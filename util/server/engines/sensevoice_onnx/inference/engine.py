import time
import json
from pathlib import Path
import numpy as np
import onnxruntime as ort
import sentencepiece as spm
from typing import List
from .audio import NumPyMelExtractor, load_audio
from .encoder import SenseVoiceEncoder
from .decoder import SenseVoiceDecoder
from .integrator import ResultIntegrator
from .radar import HotwordRadar
from .schema import ASREngineConfig, TranscriptionResult, Timings, RecognitionResult

class SenseVoiceInference:
    """
    SenseVoice ONNX 推理引擎 (纯净版)
    - 零 PyTorch 依赖
    - 动态 Prompt 构造
    - ONNX CPU/DML 支持
    """
    def __init__(self, config: ASREngineConfig):
        """
        初始化 SenseVoice 推理引擎
        只接受 ASREngineConfig 实例，所有参数均封装在其中。
        """
        self.config = config
        self.onnx_provider = config.onnx_provider
        # 1. 显式路径获取 (从外部配置直接传入)
        encoder_path = config.encoder_path
        decoder_path = config.decoder_path
        tokenizer_path = config.tokenizer_path
 
        # 2. 构造编码器、解码器与前端
        self.encoder = SenseVoiceEncoder(
            encoder_path=encoder_path, 
            onnx_provider=self.onnx_provider,
            dml_pad_to=self.config.dml_pad_to
        )
        self.decoder = SenseVoiceDecoder(
            decoder_path=decoder_path, 
            onnx_provider=self.onnx_provider,
            dml_pad_to=self.config.dml_pad_to
        )
        self.frontend = NumPyMelExtractor()
        
        # 3. 初始化分词器 (使用 bytes 加载，避免 Windows 路径编码问题)
        self.sp = spm.SentencePieceProcessor()
        with open(tokenizer_path, 'rb') as f:
            self.sp.load_from_serialized_proto(f.read())
        
        # 4. 初始化热词雷达 (预先创建一个空雷达，之后动态更新)
        self.radar = HotwordRadar([], self.sp)
        if self.config.hotwords:
            self.update_hotwords(self.config.hotwords)
            
        # 5. 结果整合器
        self.integrator = ResultIntegrator()

    def update_hotwords(self, hotwords: List[str]):
        """更新热词列表 (仅接受字符串列表)"""
        # 动态更新现有雷达的热词模型
        self.radar.update_hotwords(hotwords)

    def __call__(self, audio_data: np.ndarray, lid="auto", itn=True, chunk_size=40, overlap=5):
        """[默认识别接口] 根据音频长度自动选择分段或直接识别"""
        return self.recognize(audio_data, lid=lid, itn=itn, chunk_size=chunk_size, overlap=overlap)

    def recognize(self, audio_data: np.ndarray, lid="auto", itn=True, chunk_size=40, overlap=5):
        """
        识别接口，支持自动分段拼接。
        - 采用统一的分片处理逻辑：短音频即为“只有一片”的长音频。
        """
        # 1. 提取全量特征
        lfr_feat = self.frontend.extract(audio_data)
        
        # 2. 计算分段 (按 LFR 帧切分)
        # 1s ≈ 16.6 帧, 这里使用更精确的 1s = 100/6 帧
        chunk_frames = int(chunk_size * 100 / 6)
        overlap_frames = int(overlap * 100 / 6)
        stride = max(1, chunk_frames - overlap_frames)
        
        all_results = []
        for start in range(0, len(lfr_feat), stride):
            end = min(start + chunk_frames, len(lfr_feat))
            chunk_lfr = lfr_feat[start:end]
            
            # 执行单段识别 (从 config 同步 Top-K)
            offset_sec = (start * 6 * 0.01) # 1帧 = 0.06s
            res = self._recognize_lfr(chunk_lfr, lid=lid, itn=itn, offset_sec=offset_sec, top_k=self.config.top_k)
            all_results.append(res)
            
            # 如果已经到达末尾，跳出
            if end == len(lfr_feat):
                break
                
        # 3. 结果流式拼接 (基于 SequenceMatcher)
        # 如果只有一片结果，_merge_results 会直接返回原对象，保留完整耗时统计。
        return self._merge_results(all_results, overlap)

    def transcribe(self, audio_file: str, lid="auto", itn=True, chunk_size=40, overlap=5, start_second=None, duration=None):
        """运行完整转录流水线 (从文件加载音频)"""
        audio = load_audio(audio_file, start_second=start_second, duration=duration)
        return self.recognize(audio, lid=lid, itn=itn, chunk_size=chunk_size, overlap=overlap)


    def _recognize_lfr(self, lfr_feat: np.ndarray, lid="auto", itn=True, offset_sec=0.0, top_k=10):
        """
        [最底层的识别逻辑] 
        接受 LFR 特征，输出带有全局时间偏移的结果。
        """
        t_start = time.perf_counter()
        
        # 1. 编码器推理
        t0 = time.perf_counter()
        enc_out = self.encoder.forward(lfr_feat, lid=lid, itn=itn)
        t_encoder = time.perf_counter() - t0
        
        # 2. 解码器推理
        t0 = time.perf_counter()
        T_valid = lfr_feat.shape[0]
        greedy_results, topk_indices, topk_probs, top1_indices = self.decoder.decode_all(
            enc_out, self.sp, top_k=top_k, T_valid=T_valid
        )
        t_decoder = time.perf_counter() - t0
        
        # 3. 热词扫描 (即便热词为空，扫描方法内部也会极速跳过)
        t0 = time.perf_counter()
        detected_hotwords = self.radar.scan(topk_indices, topk_probs, top_k=top_k)
        t_radar = time.perf_counter() - t0
        
        # 4. 整合结果
        t0 = time.perf_counter()
        integrated_list = ResultIntegrator.integrate(greedy_results, detected_hotwords)
        t_integrate = time.perf_counter() - t0
        
        recognition_results = []
        for item in integrated_list:
            recognition_results.append(RecognitionResult(
                text=item["text"], 
                start=round(item["start"] + offset_sec, 3), 
                is_hotword=item.get("is_hotword", False)
            ))
            
        t_total = time.perf_counter() - t_start
        
        return TranscriptionResult(
            text="".join([r.text for r in recognition_results]),
            results=recognition_results,
            hotwords=[h["text"] for h in detected_hotwords],
            timings=Timings(frontend=0, encoder=t_encoder, decoder=t_decoder, radar=t_radar, integrate=t_integrate, total=t_total)
        )

    def _merge_results(self, results_list: List[TranscriptionResult], overlap_sec: float):
        """
        基于 SequenceMatcher 的结果拼接算法
        """
        if not results_list: return None
        if len(results_list) == 1: return results_list[0]
        
        import difflib
        
        merged_results = list(results_list[0].results)
        
        for i in range(1, len(results_list)):
            new_res = results_list[i].results
            if not new_res: continue
            if not merged_results:
                merged_results.extend(new_res)
                continue
            
            # 1. 提取重叠文本进行比对
            # 取旧结果末尾 2 倍 overlap 时间段内的内容
            # 取新结果开头 2 倍 overlap 时间段内的内容
            overlap_window = overlap_sec * 2.0
            
            last_time = merged_results[-1].start
            prev_overlap_indices = [idx for idx, r in enumerate(merged_results) if r.start >= last_time - overlap_window]
            new_overlap_indices = [idx for idx, r in enumerate(new_res) if r.start <= new_res[0].start + overlap_window]
            
            prev_overlap_text = "".join([merged_results[idx].text for idx in prev_overlap_indices])
            new_overlap_text = "".join([new_res[idx].text for idx in new_overlap_indices])
            
            # 2. 寻找最长公共子序列
            sm = difflib.SequenceMatcher(None, prev_overlap_text, new_overlap_text)
            match = sm.find_longest_match(0, len(prev_overlap_text), 0, len(new_overlap_text))
            
            if match.size >= 1:
                # 找到 prev 的截断位置
                char_count = 0
                prev_cut_idx = prev_overlap_indices[-1] + 1
                for idx in prev_overlap_indices:
                    char_count += len(merged_results[idx].text)
                    if char_count > match.a + match.size // 2: # 在匹配中点截断
                        prev_cut_idx = idx
                        break
                
                # 找到 new 的起始位置
                char_count = 0
                new_start_idx = 0
                for idx in new_overlap_indices:
                    char_count += len(new_res[idx].text)
                    if char_count > match.b + match.size // 2:
                        new_start_idx = idx + 1
                        break
                
                # 执行拼接
                merged_results = merged_results[:prev_cut_idx] + new_res[new_start_idx:]
            else:
                # 兜底：基于时间戳硬拼接
                last_t = merged_results[-1].start
                new_start_idx = 0
                for idx, r in enumerate(new_res):
                    if r.start > last_t:
                        new_start_idx = idx
                        break
                else:
                    new_start_idx = len(new_res)
                merged_results.extend(new_res[new_start_idx:])
        
        # 汇聚所有分段中发现的热词并去重
        all_hotwords = []
        for r in results_list:
            all_hotwords.extend(r.hotwords)
        unique_hotwords = list(dict.fromkeys(all_hotwords)) # 保持插入顺序的去重
        
        return TranscriptionResult(
            text="".join([r.text for r in merged_results]),
            results=merged_results,
            hotwords=unique_hotwords,
            timings=Timings(0, 0, 0, 0, 0, 0) # 拼接后的汇总耗时暂时忽略
        )
