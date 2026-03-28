import onnxruntime
import numpy as np
import base64
import os
import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
from . import logger

@dataclass
class Token:
    text: str
    start: float

class CTCDecoder:
    """FunASR CTC 推理与解码器 (合并低层引擎与高层策略)"""
    def __init__(self, model_path: str, tokens_path: str, dml_enable: bool = True, pad_to: int = 30, corrector: Optional[Any] = None):
        self.model_path = model_path
        self.tokens_path = tokens_path
        self.dml_enable = dml_enable
        self.pad_to = pad_to
        self.corrector = corrector
        
        self.sess = None
        self.id2token = {}
        self.input_dtype = np.float32
        
        self._initialize_session()
        self._load_tokens()
        self.warmup()

    def _initialize_session(self):
        session_opts = onnxruntime.SessionOptions()
        session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        providers = ['CPUExecutionProvider']
        if self.dml_enable and 'DmlExecutionProvider' in onnxruntime.get_available_providers():
            providers.insert(0, 'DmlExecutionProvider') 
            
        logger.info(f"[CTC] 加载模型: {os.path.basename(self.model_path)} (Providers: {providers})")
        
        self.sess = onnxruntime.InferenceSession(
            self.model_path, 
            sess_options=session_opts, 
            providers=providers
        )
        
        # 检测模型输入精度
        in_type = self.sess.get_inputs()[0].type
        self.input_dtype = np.float16 if 'float16' in in_type else np.float32

    def _load_tokens(self):
        self.id2token = load_ctc_tokens(self.tokens_path)
        logger.info(f"[CTC] 加载词表: {len(self.id2token)} tokens")

    def warmup(self):
        if self.pad_to <= 0:
            return
        target_t_lfr = int((self.pad_to * 100 + 5) // 6) + 1
        dummy_enc = np.zeros((1, target_t_lfr, 512), dtype=self.input_dtype)
        in_name = self.sess.get_inputs()[0].name
        logger.info(f"[CTC] 正在预热 (固定形状: {self.pad_to}s)...")
        self.sess.run(None, {in_name: dummy_enc})

    def decode(self, enc_output: np.ndarray, enable_ctc: bool, max_hotwords: int) -> Tuple[List[Token], List[str], Dict[str, float]]:
        """执行推理、解码和热词过滤"""
        t_stats = {"infer": 0.0, "decode": 0.0, "hotword": 0.0}
        if not enable_ctc or self.sess is None:
            return [], [], t_stats

        # 1. 执行推理
        t0 = time.perf_counter()
        ctc_logits = self.sess.run(None, {"enc_output": enc_output})[0]
        t_stats["infer"] = time.perf_counter() - t0
        
        # 2. 执行贪婪解码
        t0 = time.perf_counter()
        ctc_text, ctc_results, ctc_details = decode_ctc(ctc_logits, self.id2token)
        t_stats["decode"] = time.perf_counter() - t0
        t_stats.update(ctc_details)

        # 3. 热词过滤 (重打分)
        hotwords = []
        t0 = time.perf_counter()
        if self.corrector and self.corrector.hotwords and ctc_text:
            res = self.corrector.correct(ctc_text, k=max_hotwords)
            candidates = set()
            for _, hw, _ in res.matchs: candidates.add(hw)
            for _, hw, _ in res.similars: candidates.add(hw)
            hotwords = list(candidates)
        t_stats["hotword"] = time.perf_counter() - t0
            
        return ctc_results, hotwords, t_stats


def load_ctc_tokens(filename):
    """加载 CTC 词表"""
    id2token = dict()
    if not os.path.exists(filename):
        return id2token
    with open(filename, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            if len(parts) == 1:
                t, i = " ", parts[0]
            else:
                t, i = parts
            
            # Pre-decode base64 here to save time during inference
            try:
                # Some tokens might rely on being decoded, do it once
                token_text = base64.b64decode(t).decode("utf-8")
            except:
                token_text = t
                
            id2token[int(i)] = token_text
                
    return id2token

def decode_ctc(logits, id2token):
    """
    Greedy search 贪心解码。
    
    Args:
        logits: 模型输出的概率分布 (T, V) 或已经是 indices (T,)
        id2token: 词表映射 dict
    """
    # [OPTIMIZATION] 如果输入已经是 1D 数组或 (1, T)，说明是已经融合了 ArgMax 的 indices
    if logits.ndim == 1 or (logits.ndim == 2 and logits.shape[0] == 1):
        indices = logits.flatten()
        t_cast = 0.0
        t_argmax = 0.0
    else:
        # [Legacy] 兼容输出原始 Logits 的情况
        # 优化策略：先转 float32，避免在 float16 上做大规模 argmax 的潜在精度问题或性能抖动
        t_s = time.perf_counter()
        logits_f32 = logits.astype(np.float32)
        t_cast = time.perf_counter() - t_s
        
        t_s = time.perf_counter()
        indices = np.argmax(logits_f32, axis=-1).flatten()
        t_argmax = time.perf_counter() - t_s
        
    t0 = time.perf_counter() # 重置计数以精确测量循环耗时
    blank_id = max(id2token.keys()) if id2token else 0
    
    frame_shift_ms = 60
    offset_ms = -240
    
    # 1. Collapse repeats
    collapsed = []
    if len(indices) > 0:
        current_id = indices[0]
        start_idx = 0
        for i in range(1, len(indices)):
            if indices[i] != current_id:
                collapsed.append((current_id, start_idx))
                current_id = indices[i]
                start_idx = i
        collapsed.append((current_id, start_idx))

    results = []

    # 2. Filter blanks and decode text
    for token_id, start in collapsed:
        if token_id == blank_id:
            continue

        token_text = id2token.get(token_id, "")
        if not token_text: continue

        # Calculate time (只计算起始位置)
        t_start = max((start * frame_shift_ms + offset_ms) / 1000.0, 0.0)

        results.append(Token(
            text=token_text,
            start=t_start
        ))
                
    full_text = "".join([r.text for r in results])
    t_loop = time.perf_counter() - t0
    
    timings = {
        "cast": t_cast,
        "argmax": t_argmax,
        "loop": t_loop
    }
    return full_text, results, timings

def align_timestamps(ctc_results, llm_text):
    """
    使用 Needleman-Wunsch 算法对齐 CTC 结果和 LLM 文本
    只使用起始位置进行匹配
    """
    if not ctc_results or not llm_text:
        return []

    # 1. 展开 CTC 结果为字符级别（只保留起始位置）
    ctc_chars = []
    for item in ctc_results:
        text = item.text
        start = item.start

        if len(text) > 0:
            # 假设每个字符占用相同时间间隔
            char_duration = 0.08  # 默认每个字符约 80ms
            for i, char in enumerate(text):
                c_start = start + i * char_duration
                ctc_chars.append({"char": char, "start": c_start})

    llm_chars = list(llm_text)

    n = len(ctc_chars) + 1
    m = len(llm_chars) + 1

    # Core DP Matrix
    score = np.zeros((n, m), dtype=np.float32)
    # trace: 1=diag, 2=up, 3=left
    trace = np.zeros((n, m), dtype=np.int8)

    gap_penalty = -1.0
    match_score = 1.0
    mismatch_score = -1.0

    # Init margins
    for i in range(n): score[i][0] = i * gap_penalty
    for j in range(m): score[0][j] = j * gap_penalty

    # Fill DP
    for i in range(1, n):
        for j in range(1, m):
            char_ctc = ctc_chars[i-1]["char"]
            char_llm = llm_chars[j-1]

            s_diag = score[i-1][j-1] + (match_score if char_ctc.lower() == char_llm.lower() else mismatch_score)
            s_up = score[i-1][j] + gap_penalty
            s_left = score[i][j-1] + gap_penalty

            best = max(s_diag, s_up, s_left)
            score[i][j] = best

            if best == s_diag: trace[i][j] = 1
            elif best == s_up: trace[i][j] = 2
            else: trace[i][j] = 3

    # Traceback
    llm_alignment = [None] * len(llm_chars)
    i, j = n - 1, m - 1

    while i > 0 or j > 0:
        if i > 0 and j > 0 and trace[i][j] == 1:
            llm_alignment[j-1] = ctc_chars[i-1]
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or trace[i][j] == 2):
            i -= 1
        elif j > 0 and (i == 0 or trace[i][j] == 3):
            llm_alignment[j-1] = None
            j -= 1

    # 插值填充未对齐的字符
    anchors = []
    for idx, item in enumerate(llm_alignment):
        if item is not None:
            anchors.append((idx, item["start"]))

    final_chars = []

    def get_interpolated_start(target_idx):
        """插值计算起始位置"""
        prev_a, next_a = None, None
        for a in anchors:
            if a[0] < target_idx:
                prev_a = a
            elif a[0] > target_idx:
                next_a = a
                break

        if prev_a and next_a:
            p_idx, p_start = prev_a
            n_idx, n_start = next_a

            # 线性插值
            total_gap = n_idx - p_idx
            time_gap = n_start - p_start
            step = time_gap / total_gap

            relative_step = target_idx - p_idx
            return p_start + relative_step * step
        elif prev_a:
            return prev_a[1] + 0.05  # 向后推一点
        elif next_a:
            return max(0, next_a[1] - 0.05)  # 向前推一点
        else:
            return 0.0

    for idx, char in enumerate(llm_chars):
        if llm_alignment[idx]:
            s = llm_alignment[idx]["start"]
        else:
            s = get_interpolated_start(idx)
        final_chars.append({"char": char, "start": s})

    return final_chars


