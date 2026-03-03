# coding=utf-8
import os
import time
import re
import codecs
import dataclasses
import numpy as np
import multiprocessing as mp
from pathlib import Path
from collections import deque
from typing import Optional, List

from .schema import MsgType, StreamingMessage, DecodeResult, ASREngineConfig, TranscribeResult, ForcedAlignItem, ForcedAlignResult
from .asr_worker import asr_helper_worker_proc
from .utils import normalize_language_name, validate_language
from . import llama

@dataclasses.dataclass
class ASRS_Segment:
    """管理分片记忆及其物理时间坐标"""
    idx: int
    audio_start: float
    audio_end: float
    text: str = ""
    items: List[ForcedAlignItem] = None   

class QwenASREngine:
    """Qwen3-ASR 流式转录引擎 (GGUF 后端) - 统一辅助进程架构"""
    def __init__(self, config: ASREngineConfig):
        self.config = config
        self.verbose = config.verbose
        if self.verbose: print(f"--- [QwenASR] 初始化引擎 (DML: {config.use_dml}) ---")

        from qwen_asr_gguf.inference import llama
        self.llama_mod = llama # keep reference
        
        # 路径解析
        llm_gguf = os.path.join(config.model_dir, config.llm_fn)

        
        # 1. 启动辅助子进程 (编码 + 对齐)
        self.to_worker_q = mp.Queue()
        self.from_enc_q = mp.Queue()
        self.from_align_q = mp.Queue()
        
        self.helper_proc = mp.Process(
            target=asr_helper_worker_proc, 
            args=(self.to_worker_q, self.from_enc_q, self.from_align_q, config), 
            daemon=True
        )
        self.helper_proc.start()
        
        # 2. 加载识别 LLM
        self.model = llama.LlamaModel(llm_gguf)
        self.embedding_table = llama.get_token_embeddings_gguf(llm_gguf)
        self.ctx = llama.LlamaContext(self.model, n_ctx=config.n_ctx, n_batch=4096, embeddings=False)
        
        # 3. 等待子进程就绪信号 (包含 Encoder 预热完成)
        msg = self.from_enc_q.get()
        if msg.msg_type == MsgType.MSG_ERROR:
            raise RuntimeError(f"辅助进程启动失败: \n\n{msg.data}")
            
        if msg.msg_type == MsgType.MSG_READY and self.verbose:
            print("--- [QwenASR] 辅助进程已就绪 ---")

        # 缓存 Token ID
        self.ID_IM_START = self.model.token_to_id("<|im_start|>")
        self.ID_IM_END = self.model.token_to_id("<|im_end|>")
        self.ID_AUDIO_START = self.model.token_to_id("<|audio_start|>")
        self.ID_AUDIO_END = self.model.token_to_id("<|audio_end|>")
        self.ID_ASR_TEXT = self.model.token_to_id("<asr_text>")

    def shutdown(self):
        # 向辅助进程发送停止信号
        if self.helper_proc:
            self.to_worker_q.put(StreamingMessage(MsgType.CMD_STOP))
            self.helper_proc.join()
        if self.verbose: print("--- [QwenASR] 引擎已关闭 ---")

    def _build_prompt_embd(self, audio_embd: np.ndarray, prefix_text: str, context: Optional[str], language: Optional[str]):
        """构造用于 LLM 输入的 Embedding 序列 (区块化打包模式)"""
        def tk(t): return self.model.tokenize(t)

        # 1. 区块 A: 音频之前的所有内容 (System + User Header)
        prefix_str = f"system\n{context or 'You are a helpful assistant.'}"
        prefix_tokens = [self.ID_IM_START] + tk(prefix_str) + [self.ID_IM_END] + \
                        [self.ID_IM_START] + tk("user\n") + [self.ID_AUDIO_START]
        
        # 2. 区块 B: 音频之后的所有内容 (Instruction + Assistant Header + History)
        suffix_head = f"assistant\n"
        if language: suffix_head += f"language {language}"
        
        suffix_tokens = [self.ID_AUDIO_END] + [self.ID_IM_END] + \
                        [self.ID_IM_START] + tk(suffix_head) + [self.ID_ASR_TEXT] + tk(prefix_text)

        # 3. 统计并拼接
        n_pre, n_aud, n_suf = len(prefix_tokens), audio_embd.shape[0], len(suffix_tokens)
        total_embd = np.zeros((n_pre + n_aud + n_suf, self.model.n_embd), dtype=np.float32)
        
        total_embd[:n_pre] = self.embedding_table[prefix_tokens]
        total_embd[n_pre : n_pre + n_aud] = audio_embd
        total_embd[n_pre + n_aud:] = self.embedding_table[suffix_tokens]
        
        return total_embd

    def _decode(
        self, 
        full_embd: np.ndarray,
        prefix_text: str, 
        rollback_num: int,
        is_last_chunk: bool = False, 
        temperature: float = 0.4
    ) -> DecodeResult:
        """底层方法：执行单次 LLM 生成循环（物理推理）"""
        result = DecodeResult()
        
        total_len = full_embd.shape[0]
        pos_base = np.arange(0, total_len, dtype=np.int32)
        pos_arr = np.concatenate([pos_base, pos_base, pos_base, np.zeros(total_len, dtype=np.int32)])
        batch = self.llama_mod.LlamaBatch(max(total_len * 4, 8192), self.model.n_embd, 1)
        batch.set_embd(full_embd, pos=pos_arr)
        
        # 1. Prefill
        self.ctx.clear_kv_cache()
        t_pre_start = time.time()
        self.ctx.decode(batch)
        prefill_time = time.time() - t_pre_start
        
        # 2. Generation Loop（使用新采样器和随机种子）
        t_gen_start = time.time()
        n_gen_tokens = 0
        display_queue = deque()
        stable_tokens = []
        stable_text_acc = ""
        text_decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        
        # 每次解码使用新的随机种子
        seed = int(np.random.randint(0, 2**31 - 1))
        sampler = self.llama_mod.LlamaSampler(temperature=temperature, seed=seed)
        last_sampled_token = sampler.sample(self.ctx.ptr)
        for _ in range(512): # Max new tokens per chunk
            if last_sampled_token in [self.model.eos_token, self.ID_IM_END]:
                break
            
            if self.ctx.decode_token(last_sampled_token) != 0:
                    break
            
            display_queue.append(last_sampled_token)
            if len(display_queue) > rollback_num:
                ready_token = display_queue.popleft()
                stable_tokens.append(ready_token)
                piece = text_decoder.decode(self.model.token_to_bytes(ready_token))
                if piece:
                    print(re.sub('([，。？！：,\.])', '\\1\n', piece), end='', flush=True)
                    stable_text_acc += piece
            
            # 熔断检查：检测重复循环
            if len(stable_tokens) > 15:
                if len(set(stable_tokens[-15:])) <= 3:
                    result.is_aborted = True
                    break
            
            last_sampled_token = sampler.sample(self.ctx.ptr)
            n_gen_tokens += 1
            
        gen_time = time.time() - t_gen_start
        del sampler  # 释放采样器资源
        del batch
            
        if is_last_chunk and not result.is_aborted:
            while display_queue:
                t = display_queue.popleft()
                stable_tokens.append(t)
                piece = text_decoder.decode(self.model.token_to_bytes(t))
                if piece:
                    print(re.sub('([，。？！：,\.])', '\\1\n', piece), end="", flush=True)
                    stable_text_acc += piece
            final_p = text_decoder.decode(b"", final=True)
            if final_p: 
                print(final_p, end='', flush=True)
                stable_text_acc += final_p
        
        # 填充结果（内核输出标准化）
        result.text = stable_text_acc
        result.stable_tokens = stable_tokens
        result.t_prefill = prefill_time
        result.t_generate = gen_time
        result.n_prefill = total_len
        result.n_generate = n_gen_tokens
        result.n_generate = n_gen_tokens
        return result

    def _safe_decode(
        self, 
        full_embd: np.ndarray, 
        prefix_text: str, 
        rollback_num: int, 
        is_last_chunk: bool, 
        temperature: float
    ) -> DecodeResult:
        """带熔断加温重试的高层推理封装"""
        for i in range(4):
            res = self._decode(full_embd, prefix_text, rollback_num, is_last_chunk, temperature)
            if not res.is_aborted:
                break
            temperature += 0.3
            res.text += "====解码有误，强制熔断===="
            print(f"\n\n[!] 触发重试 (Temp -> {temperature:.1f})\n")
        return res 

    def _collect_alignment(
        self, 
        idx: int, 
        all_segments: List[ASRS_Segment], 
        all_aligned_items: List[ForcedAlignItem], 
        stats: dict
    ):
        """同步回收指定索引的对齐结果并更新状态"""
        if idx < 0 or idx >= len(all_segments): return
        
        align_msg = self.from_align_q.get()
        if align_msg.msg_type == MsgType.MSG_ALIGN and align_msg.data:
            ares: ForcedAlignResult = align_msg.data
            all_segments[idx].items = ares.items
            all_aligned_items.extend(ares.items)
            if ares.performance:
                stats["align_enc_time"] += ares.performance.get("encoder_time", 0)
                stats["align_dec_time"] += ares.performance.get("decoder_time", 0)

    def _print_stats(self, stats: dict, audio_duration: float, t_total: float):
        """打印转录过程的性能统计指标"""
        rtf = t_total / audio_duration if audio_duration > 0 else 0
        pre_speed = stats["prefill_tokens"] / stats["prefill_time"] if stats["prefill_time"] > 0 else 0
        gen_speed = stats["decode_tokens"] / stats["decode_time"] if stats["decode_time"] > 0 else 0
        
        print(f"\n\n📊 性能统计:")
        print(f"  🔹 RTF (实时率) : {rtf:.3f} (越小越快)")
        print(f"  🔹 音频时长    : {audio_duration:.2f} 秒")
        print(f"  🔹 总处理耗时  : {t_total:.2f} 秒")
        print(f"  🔹 编码等待    : {stats['wait_time']:.2f} 秒")
        print(f"  🔹 对齐总时    : {stats['align_enc_time']+stats['align_dec_time']:.2f} 秒 (分段异步对齐)")
        print(f"  🔹 LLM 预填充  : {stats['prefill_time']:.3f} 秒 ({stats['prefill_tokens']} tokens, {pre_speed:.1f} tokens/s)")
        print(f"  🔹 LLM 生成    : {stats['decode_time']:.3f} 秒 ({stats['decode_tokens']} tokens, {gen_speed:.1f} tokens/s)")

    def transcribe(
        self, 
        audio_file: str, 
        language: Optional[str] = None, 
        context: Optional[str] = None, 
        start_second: float = 0.0,
        duration: float = 0.0,
        temperature: float = 0.4,
        rollback_num: int = 5
    ) -> TranscribeResult:
        """运行完整转录流水线 (从文件加载音频)"""
        from .utils import load_audio
        audio = load_audio(audio_file, start_second=start_second, duration=duration)
        
        return self.asr(
            audio=audio,
            context=context or "",
            language=language,
            chunk_size_sec=self.config.chunk_size,
            memory_chunks=self.config.memory_num,
            temperature=temperature,
            rollback_num=rollback_num
        )

    def asr(
        self, 
        audio: np.ndarray,
        context: Optional[str],
        language: Optional[str],
        chunk_size_sec: float = 40.0,
        memory_chunks: int = 2,
        temperature: float = 0.4,
        rollback_num: int = 5
    ) -> TranscribeResult:
        """运行完整转录流水线 (三级流水线：i+1 预取, i 识别, i-1 对齐)"""
        # 语言归一化与校验
        if language:
            language = normalize_language_name(language)
            validate_language(language)

        sr = 16000
        samples_per_chunk = int(chunk_size_sec * sr)
        total_len = len(audio)
        num_chunks = int(np.ceil(total_len / samples_per_chunk))
        total_duration = total_len / sr
        
        # 记忆管理 (预定义所有分片的物理边界)
        all_segments: List[ASRS_Segment] = [
            ASRS_Segment(
                idx=i,
                audio_start=i * chunk_size_sec,
                audio_end=min((i + 1) * chunk_size_sec, total_duration)
            ) for i in range(num_chunks)
        ]
        asr_memory = deque(maxlen=memory_chunks) # 存储 (embd, text)
        total_full_text = ""
        all_aligned_items: List[ForcedAlignItem] = []
        
        # 统计指标
        stats = {
            "prefill_time": 0.0, "decode_time": 0.0,
            "prefill_tokens": 0, "decode_tokens": 0,
            "wait_time": 0.0, "encode_time": 0.0,
            "align_enc_time": 0.0, "align_dec_time": 0.0
        }
        t_main_start = time.time()

        # 发送编码任务
        def send_enc(idx):
            if idx >= num_chunks: return
            s, e = idx * samples_per_chunk, min((idx + 1) * samples_per_chunk, total_len)
            data = audio[s:e]
            if len(data) < samples_per_chunk: 
                data = np.pad(data, (0, samples_per_chunk - len(data)))
            self.to_worker_q.put(StreamingMessage(MsgType.CMD_ENCODE, data=data, is_last=(idx == num_chunks - 1)))

        # 发送对齐任务
        def send_align(idx):
            if idx < 0 or idx >= len(all_segments): return
            seg = all_segments[idx]
            if not seg.text.strip():
                # 无文本时发送空结果占位，保证消息队列计数正确
                self.to_worker_q.put(StreamingMessage(MsgType.CMD_ALIGN, data=None, text="", is_last=(idx == num_chunks-1)))
                return

            # 对齐物理起点：选取“上一片最后一个字的结尾”和“分片物理起跑点前 10s”的较大值
            offset_sec = seg.audio_start
            if idx > 0 and all_segments[idx-1].items:
                last_end = all_segments[idx-1].items[-1].end_time
                prev_limit = all_segments[idx-1].audio_end 
                offset_sec = min(prev_limit, max(last_end, prev_limit - 10.0))
            
            # 对齐音频截取：从 offset 到本片物理结尾
            s_smpl, e_smpl = int(offset_sec * sr), int(seg.audio_end * sr)
            audio_slice = audio[s_smpl:e_smpl]
            
            self.to_worker_q.put(StreamingMessage(
                msg_type=MsgType.CMD_ALIGN,
                data=audio_slice,
                text=seg.text,
                offset_sec=float(offset_sec),
                language=language,
                is_last=(idx == num_chunks - 1)
            ))

        # --- 三级流水线主循环 ---
        if num_chunks > 0: send_enc(0)

        for i in range(num_chunks):
            # 1. 拿到第 i 片段音频特征
            t_w_start = time.time()
            msg = self.from_enc_q.get()
            stats["wait_time"] += (time.time() - t_w_start)
            stats["encode_time"] += msg.encode_time
            audio_feature, was_last = msg.data, msg.is_last
            
            # 2. 拿到 i-2 片段时间戳 (用以驱动 i-1 的对齐起点)
            if i >= 2: self._collect_alignment(i - 2, all_segments, all_aligned_items, stats)
            
            # 3. 触发 i+1 特征提取
            if not was_last: send_enc(i + 1)
            
            # 4. 触发 i-1 时间戳匹配
            if i >= 1: send_align(i - 1)
            
            # 5. 识别第 i 片段文字
            prefix_text = "".join([m[1] for m in asr_memory])
            combined_audio = np.concatenate([m[0] for m in asr_memory] + [audio_feature], axis=0)
            full_embd = self._build_prompt_embd(combined_audio, prefix_text, context, language)
            
            # 带熔断加温重试的解码调用
            res = self._safe_decode(full_embd, prefix_text, rollback_num, was_last, temperature)

            
            # 记忆管理
            all_segments[i].text = res.text
            asr_memory.append((audio_feature, res.text))
            
            total_full_text += res.text
            stats["prefill_tokens"] += res.n_prefill; stats["prefill_time"] += res.t_prefill
            stats["decode_tokens"] += res.n_generate; stats["decode_time"] += res.t_generate

        # --- 收尾逻辑 ---
        if num_chunks >= 2: 
            self._collect_alignment(num_chunks - 2, all_segments, all_aligned_items, stats)
            
        if num_chunks >= 1:
            send_align(num_chunks - 1)
            self._collect_alignment(num_chunks - 1, all_segments, all_aligned_items, stats)

        # 4. 结果整理
        all_aligned_items.sort(key=lambda x: x.start_time)
        t_total = time.time() - t_main_start
        if self.verbose: self._print_stats(stats, total_duration, t_total)
            
        return TranscribeResult(
            text=total_full_text,
            alignment=ForcedAlignResult(items=all_aligned_items) if all_aligned_items else None,
            performance=stats
        )
