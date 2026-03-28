# coding=utf-8
import os
import time
import unicodedata
import numpy as np
import onnxruntime as ort
import codecs
from typing import List, Dict, Any, Optional
from pathlib import Path

from .schema import ForcedAlignItem, ForcedAlignResult, AlignerConfig
from .encoder import QwenAudioEncoder
from .utils import normalize_language_name, validate_language
from . import llama
from . import logger

class AlignerProcessor:
    """文本预处理与时间戳修正逻辑"""
    def __init__(self):
        self.assets_dir = Path(__file__).parent / "assets"
        ko_dict_path = self.assets_dir / "korean_dict_jieba.dict"
        self.ko_score = {}
        if ko_dict_path.exists():
            with open(ko_dict_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        word = line.split()[0]
                        self.ko_score[word] = 1.0
        self.ko_tokenizer = None

    def is_kept_char(self, ch: str) -> bool:
        if ch == "'": return True
        cat = unicodedata.category(ch)
        return cat.startswith("L") or cat.startswith("N")

    def clean_token(self, token: str) -> str:
        return "".join(ch for ch in token if self.is_kept_char(ch))

    def is_cjk_char(self, ch: str) -> bool:
        code = ord(ch)
        return (0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or
                0x20000 <= code <= 0x2A6DF or 0x2A700 <= code <= 0x2B73F or
                0x2B740 <= code <= 0x2B81F or 0x2B820 <= code <= 0x2CEAF or
                0xF900 <= code <= 0xFAFF)

    def tokenize_japanese(self, text: str) -> List[str]:
        try:
            import nagisa
            words = nagisa.tagging(text).words
        except ImportError:
            return list(text)
        tokens = []
        for w in words:
            cleaned = self.clean_token(w)
            if cleaned: tokens.append(cleaned)
        return tokens

    def tokenize_korean(self, text: str) -> List[str]:
        if self.ko_tokenizer is None:
            try:
                from soynlp.tokenizer import LTokenizer
                self.ko_tokenizer = LTokenizer(scores=self.ko_score)
            except ImportError:
                return list(text)
        raw_tokens = self.ko_tokenizer.tokenize(text)
        tokens = []
        for w in raw_tokens:
            w_clean = self.clean_token(w)
            if w_clean: tokens.append(w_clean)
        return tokens

    def tokenize_general(self, text: str) -> List[str]:
        """通用的分词逻辑：按空格切分，且对 CJK 字符进行逐字拆分（适用于中、英、中英混排及大多数语种）"""
        tokens = []
        for seg in text.split():
            cleaned = self.clean_token(seg)
            if not cleaned: continue
            buf = []
            for ch in cleaned:
                if self.is_cjk_char(ch):
                    if buf: tokens.append("".join(buf)); buf = []
                    tokens.append(ch)
                else: buf.append(ch)
            if buf: tokens.append("".join(buf))
        return tokens

    def tokenize(self, text: str, language: Optional[str] = None) -> List[str]:
        # 统一转为小写字符串。如果为 None 则视为空字符串，从而安全进入 else 分支。
        lang = str(language or "").lower()
        if lang == "japanese": 
            return self.tokenize_japanese(text)
        elif lang == "korean": 
            return self.tokenize_korean(text)
        else: 
            # 所有的其他语种均使用通用分词逻辑
            return self.tokenize_general(text)

    def fix_timestamps(self, data: np.ndarray) -> List[int]:
        data_list = data.tolist()
        n = len(data_list)
        if n == 0: return []
        dp, parent = [1] * n, [-1] * n
        for i in range(1, n):
            for j in range(i):
                if data_list[j] <= data_list[i] and dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1; parent[i] = j
        max_idx = dp.index(max(dp))
        lis_indices, idx = [], max_idx
        while idx != -1: lis_indices.append(idx); idx = parent[idx]
        lis_indices.reverse()
        is_normal = [False] * n
        for idx in lis_indices: is_normal[idx] = True
        result = data_list.copy()
        i = 0
        while i < n:
            if not is_normal[i]:
                j = i
                while j < n and not is_normal[j]: j += 1
                anomaly_count = j - i
                left_val = next((result[k] for k in range(i-1, -1, -1) if is_normal[k]), None)
                right_val = next((result[k] for k in range(j, n) if is_normal[k]), None)
                if anomaly_count <= 2:
                    for k in range(i, j):
                        if left_val is None: result[k] = right_val
                        elif right_val is None: result[k] = left_val
                        else: result[k] = left_val if (k-i+1) <= (j-k) else right_val
                else:
                    if left_val is not None and right_val is not None:
                        step = (right_val - left_val) / (anomaly_count + 1)
                        for k in range(i, j): result[k] = int(left_val + step * (k-i+1))
                    elif left_val is not None: result[i:j] = [left_val] * anomaly_count
                    elif right_val is not None: result[i:j] = [right_val] * anomaly_count
                i = j
            else: i += 1
        return [int(res) for res in result]

    def reconcile(self, original_text: str, items: List[ForcedAlignItem]) -> List[ForcedAlignItem]:
        """
        根据原始文本和干净的对齐项，重组包含标点的时间戳序列。
        原则：低耦合、内核输出标准化。
        """
        logger.debug(f"[Aligner] --- 开始执行 reconcile ---")
        logger.debug(f"[Aligner] 原始全文: '{original_text}'")
        
        # 预先全量记录原始对齐结果
        raw_items_str = " | ".join([f"'{it.text}'({it.start_time:.3f}-{it.end_time:.3f})" for it in items])
        logger.debug(f"[Aligner] 原始对齐项列表 (总计 {len(items)} 个): [{raw_items_str}]")
        
        if not items:
            return [ForcedAlignItem(text=original_text, start_time=0.0, end_time=0.0)] if original_text else []

        reconciled = []
        curr_ptr = 0
        last_ts = items[0].start_time

        for i, item in enumerate(items):
            logger.debug(f"[Aligner] 处理原始项 idx={i}: '{item.text}' [{item.start_time:.3f}s - {item.end_time:.3f}s]")
            # 搜索当前 item.text 在 original_text 中的位置 (跳过非保留字符)
            start_pos, end_pos = self._find_token_indices(original_text, item.text, curr_ptr)
            
            if start_pos != -1:
                # 1. 处理间隙项 (标点/空格)
                if start_pos > curr_ptr:
                    gap_text = original_text[curr_ptr:start_pos]
                    logger.debug(f"[Aligner] 间隙项: '{gap_text}' at [{curr_ptr}:{start_pos}]")
                    reconciled.append(ForcedAlignItem(
                        text=gap_text,
                        start_time=last_ts,
                        end_time=last_ts # 修改处：对齐到左侧字的结束
                    ))
                
                # 2. 对其后的项使用原始文本中的形态
                matched_text = original_text[start_pos:end_pos]
                logger.debug(f"[Aligner] 匹配成功 idx={i}: '{item.text}' -> '{matched_text}' at [{start_pos}:{end_pos}]")
                reconciled.append(ForcedAlignItem(
                    text=matched_text,
                    start_time=item.start_time,
                    end_time=item.end_time
                ))
                
                curr_ptr = end_pos
                last_ts = item.end_time
            else:
                logger.warning(f"[Aligner] 降级匹配 idx={i}: 无法在文本中找到 Token '{item.text}'，起始位置={curr_ptr}")
                # 降级：若无法匹配则保持原样
                reconciled.append(item)
                last_ts = item.end_time

        # 3. 处理末尾残余
        if curr_ptr < len(original_text):
            reconciled.append(ForcedAlignItem(
                text=original_text[curr_ptr:],
                start_time=last_ts,
                end_time=last_ts
            ))

        return reconciled

    def _find_token_indices(self, text: str, target: str, start_index: int):
        """寻找包含 target 的最小区间，允许穿插非保留字符"""
        target_len = len(target)
        if target_len == 0: return -1, -1
        
        txt_len = len(text)
        t_ptr = 0
        first_match = -1
        
        i = start_index
        while i < txt_len:
            ch = text[i]
            if ch == target[t_ptr]:
                if t_ptr == 0: first_match = i
                t_ptr += 1
                if t_ptr == target_len:
                    return first_match, i + 1
            elif self.is_kept_char(ch):
                if first_match != -1:
                    # 发生了回退
                    logger.debug(f"[Aligner] Token 匹配回退: target='{target}' at text[{i}]='{ch}'，回退到 {first_match}")
                    i = first_match 
                    first_match = -1
                    t_ptr = 0
            i += 1
        
        logger.debug(f"[Aligner] Token 查找失败: target='{target}', start_from={start_index}, context='{text[start_index:start_index+50]}...'")
        return -1, -1

class QwenForcedAligner:
    """Qwen3 强制对齐器 (GGUF 后端)"""
    def __init__(self, config: AlignerConfig):
        # Split Model Paths
        fe_path = os.path.join(config.model_dir, config.encoder_frontend_fn)
        be_path = os.path.join(config.model_dir, config.encoder_backend_fn)
        
        llm_gguf = os.path.join(config.model_dir, config.llm_fn)
        use_dml = config.use_dml

        # 1. 初始化统一编码器 (内部包含 5s 分片预热)
        # 使用 Split 模式
        self.encoder = QwenAudioEncoder(
            frontend_path=fe_path,
            backend_path=be_path, # 传入 backend
            use_dml=use_dml,
            warmup_sec=5.0,
            verbose=False
        )

        # 2. 加载对齐 LLM
        self.model = llama.LlamaModel(llm_gguf, n_gpu_layers=-1)
        self.embedding_table = llama.get_token_embeddings_gguf(llm_gguf)
        self.ctx = llama.LlamaContext(self.model, n_ctx=config.n_ctx, n_batch=2048, embeddings=False)
        
        self.processor = AlignerProcessor()
        self.ID_AUDIO_START = self.model.token_to_id("<|audio_start|>")
        self.ID_AUDIO_END = self.model.token_to_id("<|audio_end|>")
        self.ID_TIMESTAMP = self.model.token_to_id("<timestamp>")
        self.STEP_MS = 80.0

    def align(self, audio: np.ndarray, text: str, language: str = "Chinese", offset_sec: float = 0.0) -> ForcedAlignResult:
        """执行强制对齐，支持起始偏移量叠加"""
        # 语言归一化与校验
        if language:
            language = normalize_language_name(language)
            validate_language(language)

        t_start = time.time()
        
        # 1. 编码 (Encoder Stage) - 使用统一编码器
        audio_embd, t_enc = self.encoder.encode(audio)

        # 2. 分词与构建 Prompt (必须完整注入音频序列)
        words = self.processor.tokenize(text, language)
        def tk(t): return self.model.tokenize(t)
        
        pre_ids = [self.ID_AUDIO_START]
        post_ids = [self.ID_AUDIO_END]
        ts_positions = []
        
        # 官方结构: <audio> + word1 + <TS1> + <TS2> + word2 + <TS3> + <TS4> ...
        prefix_len = len(pre_ids) + audio_embd.shape[0] + len(post_ids)
        current_post_len = 0
        for word in words:
            word_tokens = tk(word)
            post_ids.extend(word_tokens)
            current_post_len += len(word_tokens)
            
            # 记录第一个 TS 坐标 (Start)
            ts_positions.append(prefix_len + current_post_len) 
            post_ids.append(self.ID_TIMESTAMP)
            current_post_len += 1
            
            # 记录第二个 TS 坐标 (End)
            ts_positions.append(prefix_len + current_post_len)
            post_ids.append(self.ID_TIMESTAMP)
            current_post_len += 1

        # 构建最终全量序列
        n_total = len(pre_ids) + audio_embd.shape[0] + len(post_ids)
        full_embd = np.zeros((n_total, self.model.n_embd), dtype=np.float32)
        full_embd[:len(pre_ids)] = self.embedding_table[pre_ids]
        full_embd[len(pre_ids):len(pre_ids)+audio_embd.shape[0]] = audio_embd
        full_embd[len(pre_ids)+audio_embd.shape[0]:] = self.embedding_table[post_ids]

        # 3. 推理获取 Logits (Decoder Stage)
        t_dec_start = time.time()
        pos_base = np.arange(n_total, dtype=np.int32)
        pos_arr = np.concatenate([pos_base, pos_base, pos_base, np.zeros(n_total, dtype=np.int32)])
        batch = llama.LlamaBatch(n_total * 4, embd_dim=1024)
        batch.set_embd(full_embd, pos=pos_arr)
        for idx in ts_positions: batch.logits[idx] = 1 # 只计算 timestamp 处的 logits 以提速
        
        self.ctx.clear_kv_cache()
        self.ctx.decode(batch)
        t_dec = time.time() - t_dec_start
        
        # 4. 解析结果
        raw_ts = []
        for idx in ts_positions:
            logits_ptr = self.ctx.get_logits_ith(batch.n_tokens - (n_total - idx)) # 对应 batch 中的索引
            logits = np.ctypeslib.as_array(logits_ptr, shape=(152064,))
            raw_ts.append(np.argmax(logits[:4000]))
        del batch
        
        fixed_ts = self.processor.fix_timestamps(np.array(raw_ts))
        ms = np.array(fixed_ts) * self.STEP_MS
        items = [
            ForcedAlignItem(
                text=w, 
                start_time=ms[i*2]/1000.0 + offset_sec, 
                end_time=ms[i*2+1]/1000.0 + offset_sec
            ) 
            for i, w in enumerate(words)
        ]
        
        # 5. [后处理] 将缺失的标点符号和空格找回来，并补全时间戳
        final_items = self.processor.reconcile(text, items)
        
        t_total = time.time() - t_start

        return ForcedAlignResult(
            items=final_items,
            performance={
                "encoder_time": t_enc,
                "decoder_time": t_dec,
                "total_time": t_total
            }
        )

