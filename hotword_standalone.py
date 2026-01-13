# coding: utf-8
"""
CapsWriter-Offline 独立热词与纠错系统 (Portable Version)

本展示脚本完整整合了以下模块的核心逻辑：
1. Phoneme 处理 (algo_phoneme.py)
2. 相似度算法 (algo_calc.py)
3. FastRAG 检索 (rag_fast.py)
4. 拼音纠错器 (hot_phoneme.py)
5. 纠错历史 RAG (hot_rectification.py)

数据准备和输出方式参照自 hotword_system_demo.ipynb。
性能测试部分已保留。
"""

import sys
import os
import re
import time
import threading
import logging
import json
import requests
from typing import List, Tuple, Dict, Set, Union, Literal, Optional, NamedTuple
from dataclasses import dataclass
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 确保控制台输出 UTF-8
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

# --- 依赖库导入 ---
try:
    from pypinyin import pinyin, Style
except ImportError:
    pinyin = None; Style = None

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

# =============================================================================
# 1. Phoneme 处理 (来自 algo_phoneme.py)
# =============================================================================

@dataclass(frozen=True, slots=True)
class Phoneme:
    value: str
    lang: Literal['zh', 'en', 'num', 'other']
    is_word_start: bool = False
    is_word_end: bool = False
    char_start: int = 0
    char_end: int = 0

    @property
    def is_tone(self) -> bool: return self.value.isdigit()
    @property
    def info(self) -> Tuple[str, str, bool, bool, bool, int, int]:
        return (self.value, self.lang, self.is_word_start, self.is_word_end, self.is_tone, self.char_start, self.char_end)

def normalize_text(text: str) -> str:
    res = []; prev = ''
    for c in text:
        if c.isalnum() or '\u4e00' <= c <= '\u9fff':
            if c.isupper() and prev.islower(): res.append(' ')
            elif c.isdigit() and prev.isalpha(): res.append(' ')
            elif prev.isdigit() and c.isalpha(): res.append(' ')
            res.append(c.lower()); prev = c
        else:
            if res and res[-1] != ' ': res.append(' ')
            prev = ''
    return "".join(res).strip()

def split_mixed_label(text: str) -> List[str]:
    tokens = []; s = text.lower()
    while s:
        if s[0] == ' ': s = s[1:]; continue
        m = re.match(r'[a-z]+', s)
        if m: tokens.append(m.group(0)); s = s[len(m.group(0)):]
        else:
            m = re.match(r'[0-9]+', s)
            if m: tokens.append(m.group(0)); s = s[len(m.group(0)):]
            else: tokens.append(s[0]); s = s[1:]
    return tokens

def _zh_char_to_phonemes(char: str) -> List[Phoneme]:
    if not pinyin: return [Phoneme(char, 'zh', is_word_start=True, is_word_end=True)]
    try:
        pi = pinyin(char, style=Style.INITIALS, strict=False)
        pf = pinyin(char, style=Style.FINALS, strict=False)
        pt = pinyin(char, style=Style.TONE3, neutral_tone_with_five=True)
        if not pt or not pt[0]: return [Phoneme(char, 'zh', is_word_start=True, is_word_end=True)]
        res = []
        has_init = pi and pi[0] and pi[0][0]
        if has_init: res.append(Phoneme(pi[0][0], 'zh', is_word_start=True))
        if pf and pf[0] and pf[0][0]: res.append(Phoneme(pf[0][0], 'zh', is_word_start=not has_init))
        tone = pt[0][0][-1] if pt[0][0][-1].isdigit() else '5'
        res.append(Phoneme(tone, 'zh', is_word_end=True))
        return res
    except: return [Phoneme(char, 'zh', is_word_start=True, is_word_end=True)]

def get_phoneme_seq(text: str) -> List[Phoneme]:
    normalized = normalize_text(text)
    seq = []
    for token in split_mixed_label(normalized):
        if re.match(r'^[a-z0-9]+$', token):
            lang = 'num' if token.isdigit() else 'en'
            seq.append(Phoneme(token, lang, is_word_start=True, is_word_end=True))
        elif len(token) == 1: seq.extend(_zh_char_to_phonemes(token))
        else: seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
    return seq

def get_phoneme_info(text: str, split_char: bool = True) -> List[Phoneme]:
    if not pinyin: return [Phoneme(c, 'zh', char_start=i, char_end=i+1) for i, c in enumerate(text)]
    seq = []; pos = 0
    while pos < len(text):
        c = text[pos]
        if '\u4e00' <= c <= '\u9fff':
            start = pos; pos += 1
            while pos < len(text) and '\u4e00' <= text[pos] <= '\u9fff': pos += 1
            frag = text[start:pos]
            try:
                pi = pinyin(frag, style=Style.INITIALS, strict=False)
                pf = pinyin(frag, style=Style.FINALS, strict=False)
                pt = pinyin(frag, style=Style.TONE3, neutral_tone_with_five=True)
                for i in range(min(len(frag), len(pi), len(pf), len(pt))):
                    idx = start + i; init, fin, tone = pi[i][0], pf[i][0], pt[i][0]
                    if init: seq.append(Phoneme(init, 'zh', is_word_start=True, char_start=idx, char_end=idx+1))
                    if fin: seq.append(Phoneme(fin, 'zh', is_word_start=not init, char_start=idx, char_end=idx+1))
                    if tone and tone[-1].isdigit(): seq.append(Phoneme(tone[-1], 'zh', is_word_end=True, char_start=idx, char_end=idx+1))
            except: 
                for i, char in enumerate(frag): seq.append(Phoneme(char, 'zh', is_word_start=True, is_word_end=True, char_start=start+i, char_end=start+i+1))
        elif 'a' <= c.lower() <= 'z' or '0' <= c <= '9':
            start = pos; pos += 1
            while pos < len(text):
                cur = text[pos]
                if not ('a' <= cur.lower() <= 'z' or '0' <= cur <= '9'): break
                if (text[pos-1].islower() and cur.isupper()) or (text[pos-1].isalpha() and cur.isdigit()) or (text[pos-1].isdigit() and cur.isalpha()): break
                pos += 1
            token = text[start:pos].lower(); lang = 'num' if token.isdigit() else 'en'
            if split_char:
                for i, char in enumerate(token): seq.append(Phoneme(char, lang, is_word_start=(i==0), is_word_end=(i==len(token)-1), char_start=start+i, char_end=start+i+1))
            else: seq.append(Phoneme(token, lang, is_word_start=True, is_word_end=True, char_start=start, char_end=pos))
        else: pos += 1
    return seq

# =============================================================================
# 2. 相似度算法 (来自 algo_calc.py)
# =============================================================================

SIMILAR_PHONEMES = [{'an', 'ang'}, {'en', 'eng'}, {'in', 'ing'}, {'ian', 'iang'}, {'uan', 'uang'}, {'z', 'zh'}, {'c', 'ch'}, {'s', 'sh'}, {'l', 'n'}, {'f', 'h'}, {'ai', 'ei'}]

def get_phoneme_cost(p1: Phoneme, p2: Phoneme) -> float:
    if p1.lang != p2.lang: return 1.0
    if p1.value == p2.value: return 0.0
    if p1.lang == 'zh' and p2.lang == 'zh':
        pair = {p1.value, p2.value}
        for s in SIMILAR_PHONEMES:
            if pair.issubset(s): return 0.5
    if p1.lang == 'en' and p2.lang == 'en':
        lcs_len = _lcs_length(p1.value, p2.value)
        max_len = max(len(p1.value), len(p2.value))
        return 1.0 - (lcs_len / max_len)
    return 1.0

def find_best_match(main_seq: List[Phoneme], sub_seq: List[Phoneme]) -> Tuple[float, int, int]:
    n, m = len(sub_seq), len(main_seq)
    if n == 0 or m == 0: return 0.0, 0, 0
    valid_starts = [j for j in range(m) if main_seq[j].is_word_start]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        if j not in valid_starts: dp[0][j] = float('inf')
    for i in range(1, n + 1): dp[i][0] = dp[i-1][0] + 1.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = get_phoneme_cost(sub_seq[i-1], main_seq[j-1])
            dp[i][j] = min(dp[i-1][j] + 1.0, dp[i][j-1] + 1.0, dp[i-1][j-1] + cost)
    min_dist, end_pos, best_start = float('inf'), 0, 0
    for j in range(1, m + 1):
        if dp[n][j] < min_dist:
            curr_i, curr_j = n, j
            while curr_i > 0:
                cost = get_phoneme_cost(sub_seq[curr_i-1], main_seq[curr_j-1])
                if curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j-1] + cost)) < 1e-9:
                    curr_i -= 1; curr_j -= 1
                elif abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j] + 1.0)) < 1e-9: curr_i -= 1
                elif curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i][curr_j-1] + 1.0)) < 1e-9: curr_j -= 1
                else: curr_i -= 1
            if curr_j in valid_starts:
                min_dist = dp[n][j]; end_pos = j; best_start = curr_j
    score = 1.0 - (min_dist / n)
    return score, best_start, end_pos

def test_pair(input_text, hotword, split_char=True):
    print(f"--- Testing: '{input_text}' vs '{hotword}' ---")
    input_seq = get_phoneme_info(input_text, split_char=split_char)
    target_seq = get_phoneme_info(hotword, split_char=split_char)
    print(f"Input Seq: {[p.value for p in input_seq]}")
    print(f"Target Seq: {[p.value for p in target_seq]}")
    score, start, end = find_best_match(input_seq, target_seq)
    print(f"Score: {score:.4f}")
    if score > 0:
        matched_segment = input_seq[start:end]
        print(f"Matched Segment: {[p.value for p in matched_segment]}")
    print("\n")

def _lcs_length(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    if m < n: s1, s2 = s2, s1; m, n = n, m
    if n == 0: return 0
    prev = [0] * (n + 1); curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            curr[j] = prev[j-1] + 1 if s1[i-1] == s2[j-1] else max(prev[j], curr[j-1])
        prev, curr = curr, prev
    return prev[n]

def _get_tuple_cost(t1: Tuple, t2: Tuple) -> float:
    if t1[1] != t2[1]: return 1.0
    if t1[0] == t2[0]: return 0.0
    if t1[1] == 'zh':
        pair = {t1[0], t2[0]}
        for s in SIMILAR_PHONEMES:
            if pair.issubset(s): return 0.5
    if t1[1] == 'en':
        lcs = _lcs_length(t1[0], t2[0])
        max_len = max(len(t1[0]), len(t2[0]))
        if max_len > 0: return 1.0 - (lcs / max_len)
    return 1.0

def fuzzy_substring_distance(seq1: Union[List[Phoneme], List[Tuple]], seq2: Union[List[Phoneme], List[Tuple]]) -> float:
    n, m = len(seq1), len(seq2)
    if n == 0: return 0.0
    if m == 0: return float(n)
    t1 = [p.info if isinstance(p, Phoneme) else p for p in seq1]
    t2 = [p.info if isinstance(p, Phoneme) else p for p in seq2]
    prev = [0.0] * (m + 1); curr = [0.0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = float(i)
        for j in range(1, m + 1):
            cost = _get_tuple_cost(t1[i-1], t2[j-1])
            curr[j] = min(prev[j]+1.0, curr[j-1]+1.0, prev[j-1]+cost)
        prev, curr = curr, prev
    return min(prev)

def fuzzy_substring_score(seq1, seq2) -> float:
    n = len(seq1)
    if n == 0: return 0.0
    dist = fuzzy_substring_distance(seq1, seq2)
    return max(0.0, 1.0 - (dist / n))

# =============================================================================
# 3. FastRAG 检索 (来自 rag_fast.py)
# =============================================================================

if HAS_NUMBA and HAS_NUMPY:
    @njit(cache=True)
    def _fuzzy_substring_numba(main, sub):
        n, m = len(sub), len(main)
        if n == 0 or m == 0: return float(n)
        dp = np.zeros((n+1, m+1), dtype=np.float32)
        for i in range(1, n+1): dp[i, 0] = float(i)
        for i in range(1, n+1):
            for j in range(1, m+1):
                cost = 0.0 if sub[i-1] == main[j-1] else 1.0
                dp[i, j] = min(dp[i-1, j]+1.0, dp[i, j-1]+1.0, dp[i-1, j-1]+cost)
        return np.min(dp[n, 1:])

class FastRAG:
    def __init__(self, threshold=0.6):
        self.threshold = threshold
        self.ph_to_id = {}; self.index = defaultdict(list); self.hotword_count = 0
    def _encode(self, phs: List[Phoneme]):
        ids = []
        for p in phs:
            if p.value not in self.ph_to_id: self.ph_to_id[p.value] = len(self.ph_to_id) + 1
            ids.append(self.ph_to_id[p.value])
        return np.array(ids, dtype=np.int32) if HAS_NUMPY else ids
    def add_hotwords(self, hotwords: Dict[str, List[Phoneme]]):
        for hw, phs in hotwords.items():
            if not phs: continue
            codes = self._encode(phs)
            for i in range(min(len(codes), 2)): self.index[codes[i]].append((hw, codes))
            self.hotword_count += 1
    def search(self, input_phs: List[Phoneme], top_k=10):
        if not input_phs: return []
        input_codes = self._encode(input_phs); unique = set(input_codes); candidates = []
        for c in unique: candidates.extend(self.index.get(c, []))
        seen = set(); results = []
        for hw, cands in candidates:
            if hw in seen or len(cands) > len(input_codes) + 3: continue
            seen.add(hw)
            if HAS_NUMBA and HAS_NUMPY: dist = _fuzzy_substring_numba(input_codes, cands)
            else: dist = self._python_dist(input_codes, cands)
            score = 1.0 - (dist / len(cands))
            if score >= self.threshold: results.append((hw, round(float(score), 3)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    def _python_dist(self, main, sub):
        n, m = len(sub), len(main)
        dp = [[0.0] * (m+1) for _ in range(n+1)]
        for i in range(1, n+1): dp[i][0] = float(i)
        for i in range(1, n+1):
            for j in range(1, m+1):
                cost = 0.0 if sub[i-1] == main[j-1] else 1.0
                dp[i][j] = min(dp[i-1][j]+1.0, dp[i][j-1]+1.0, dp[i-1][j-1]+cost)
        return min(dp[n][1:])

# =============================================================================
# 4. 拼音纠错器 (来自 hot_phoneme.py)
# =============================================================================

class MatchResult(NamedTuple):
    start: int; end: int; score: float; hotword: str

class CorrectionResult(NamedTuple):
    text: str; matchs: List[Tuple[str, float]]; similars: List[Tuple[str, float]]

class PhonemeCorrector:
    def __init__(self, threshold: float = 0.7, similar_threshold: float = None):
        self.threshold = threshold
        self.similar_threshold = similar_threshold if similar_threshold is not None else threshold - 0.2
        self.max_diff = 2
        self.top_k_candidates = 100
        self.hotwords: Dict[str, List[Phoneme]] = {}
        self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
        self._lock = threading.Lock()

    def update_hotwords(self, hotword_text: str) -> int:
        lines = [l.strip() for l in hotword_text.splitlines() if l.strip() and not l.strip().startswith('#')]
        new_hotwords = {}
        for hw in lines:
            phons = get_phoneme_info(hw)
            if phons: new_hotwords[hw] = phons
        with self._lock:
            self.hotwords = new_hotwords
            self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
            self.fast_rag.add_hotwords(new_hotwords)
        return len(new_hotwords)

    def load_hotwords_file(self, path: str) -> int:
        """从文件加载热词"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return self.update_hotwords(f.read())
        return 0

    def _find_matches(self, fast_results: List, input_processed: List[Tuple]) -> Tuple[List[MatchResult], List[MatchResult]]:
        matches = []; similars = []; input_len = len(input_processed)
        for hw, score in fast_results:
            hw_phonemes = self.hotwords[hw]
            hw_compare = [p.info[:5] for p in hw_phonemes]
            target_len = len(hw_compare)
            if target_len > input_len: continue
            for i in range(input_len - target_len + 1):
                sub_seg = input_processed[i : i + target_len]
                if sub_seg[0][1] != 'en' and sub_seg[0][0] != hw_compare[0][0]: continue
                if not sub_seg[0][2]: continue
                is_end_ok = False
                if sub_seg[-1][3]: is_end_ok = True
                else:
                    next_idx = i + target_len
                    if next_idx < input_len:
                        next_info = input_processed[next_idx]
                        if next_info[1] == 'zh' and next_info[4] and next_info[3]: is_end_ok = True
                if not is_end_ok: continue
                current_score = fuzzy_substring_score(hw_compare, sub_seg)
                m = MatchResult(sub_seg[0][5], sub_seg[-1][6], current_score, hw)
                similars.append(m)
                if current_score >= self.threshold: matches.append(m)
        seen = set()
        similars.sort(key=lambda x: x.score, reverse=True)
        similars = [p for p in similars if p.score >= self.similar_threshold]
        similars = [m for m in similars if not (m.hotword in seen or seen.add(m.hotword))]
        return matches, similars

    def _resolve_and_replace(self, text: str, matches: List[MatchResult]) -> Tuple[str, List[Tuple[str, float]], List[Tuple[str, float]]]:
        matches.sort(key=lambda x: (x.score, x.end - x.start), reverse=True)
        final_matches = []; all_matched_info = []; occupied_ranges = []; seen_hw_score = set()
        for m in matches:
            if (m.hotword, m.score) not in seen_hw_score:
                all_matched_info.append((m.hotword, m.score)); seen_hw_score.add((m.hotword, m.score))
            if m.score < self.threshold: continue
            if any(not (m.end <= rs or m.start >= re) for rs, re in occupied_ranges): continue
            if text[m.start : m.end] != m.hotword: final_matches.append(m)
            occupied_ranges.append((m.start, m.end))
        final_matches.sort(key=lambda x: x.start, reverse=True)
        result_list = list(text)
        for m in final_matches: result_list[m.start : m.end] = list(m.hotword)
        return "".join(result_list), [(m.hotword, m.score) for m in final_matches], all_matched_info

    def correct(self, text: str, k: int = 10) -> CorrectionResult:
        if not text or not self.hotwords: return CorrectionResult(text, [], [])
        input_phonemes = get_phoneme_info(text)
        if not input_phonemes: return CorrectionResult(text, [], [])
        with self._lock:
            fast_results = self.fast_rag.search(input_phonemes, top_k=100)
            input_processed = [p.info for p in input_phonemes]
            matches, similars = self._find_matches(fast_results, input_processed)
        new_text, final_hw_info, all_hw_info = self._resolve_and_replace(text, matches)
        sims = [(m.hotword, m.score) for m in similars[:k]]
        return CorrectionResult(new_text, final_hw_info, sims)

# =============================================================================
# 5. 纠错历史 RAG (来自 hot_rectification.py)
# =============================================================================

@dataclass
class Fragment:
    text: str; source_text: str; start: int; end: int

def _get_word_boundaries(text: str) -> List[Tuple[int, int, str]]:
    bounds = []; i, n = 0, len(text)
    while i < n:
        if not (text[i].isalnum() or '\u4e00' <= text[i] <= '\u9fff'): i += 1; continue
        start = i
        if '\u4e00' <= text[i] <= '\u9fff': i += 1
        elif text[i].isalnum():
            low = text[i].islower()
            while i < n and text[i].isalnum():
                if text[i].isupper() and low and i > start: break
                low = text[i].islower(); i += 1
        bounds.append((start, i, text[start:i]))
    return bounds

def _expand_by_words(text: str, start: int, end: int, expand_count: int = 1) -> Tuple[int, int]:
    bounds = _get_word_boundaries(text)
    start_idx = next((i for i, b in enumerate(bounds) if b[0] == start), None)
    end_idx = next((i + 1 for i, b in enumerate(bounds) if b[1] == end), None)
    if start_idx is None or end_idx is None: return start, end
    new_start = bounds[max(0, start_idx - expand_count)][0]
    new_end = bounds[min(len(bounds), end_idx + expand_count) - 1][1]
    return new_start, new_end

def _extract_continuous_fragment(bounds, start_idx, end_idx, original_text):
    if start_idx >= end_idx or start_idx >= len(bounds): return ""
    return original_text[bounds[start_idx][0] : bounds[end_idx - 1][1]]

def extract_diff_fragments(wrong, right, zh_min_phonemes=4, expand_words=1):
    wb = _get_word_boundaries(wrong); rb = _get_word_boundaries(right)
    m = SequenceMatcher(None, [b[2] for b in wb], [b[2] for b in rb])
    frags = []
    for tag, i1, i2, j1, j2 in m.get_opcodes():
        if tag in ('replace', 'delete') and i2 > i1:
            txt = _extract_continuous_fragment(wb, i1, i2, wrong)
            if txt: frags.append(Fragment(txt, wrong, wb[i1][0], wb[i2-1][1]))
        if tag in ('replace', 'insert') and j2 > j1:
            txt = _extract_continuous_fragment(rb, j1, j2, right)
            if txt: frags.append(Fragment(txt, right, rb[j1][0], rb[j2-1][1]))
    res = []
    for f in frags:
        phs = get_phoneme_seq(f.text)
        if not phs: continue
        if any(p.lang != 'zh' for p in phs) or len(phs) >= zh_min_phonemes: res.append(f.text)
        else:
            s, e = _expand_by_words(f.source_text, f.start, f.end, expand_words)
            exp = f.source_text[s:e]; res.append(exp if exp else f.text)
    return list(dict.fromkeys(res))

class RectifyRecord:
    def __init__(self, wrong, right, fragments):
        self.wrong = wrong; self.right = right; self.fragments = fragments
        self.fragment_phonemes = {f: get_phoneme_seq(f) for f in fragments}

class RectificationRAG:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold; self.records: List[RectifyRecord] = []; self._lock = threading.Lock()
    def load_rectify_text(self, text: str):
        new_records = []
        for block in text.split('---'):
            lines = [l.strip() for l in block.split('\n') if l.strip() and not l.strip().startswith('#')]
            if len(lines) >= 2:
                w, r = lines[0], lines[1]
                frags = extract_diff_fragments(w, r) or [w]
                new_records.append(RectifyRecord(w, r, frags))
        with self._lock: self.records = new_records
    def load_rectify_file(self, path: str):
        """从文件加载纠错历史"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.load_rectify_text(f.read())

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        if not text or not self.records: return []
        in_phs = get_phoneme_seq(text)
        if not in_phs: return []
        matches = []
        with self._lock:
            for rec in self.records:
                best = 0.0
                for fphs in rec.fragment_phonemes.values():
                    if not fphs: continue
                    score = fuzzy_substring_score(fphs, in_phs)
                    if score > best: best = score
                if best >= self.threshold: matches.append((rec.wrong, rec.right, round(best, 3)))
        return sorted(matches, key=lambda x: x[2], reverse=True)[:top_k]

# =============================================================================
# 6. LLM 集成 (Prompt Builder & Ollama Client)
# =============================================================================

class PromptBuilder:
    def __init__(self, system_prompt: str = "你是一个输入法纠错助手。"):
        self.system_prompt = system_prompt
        self.prompt_prefix_hotwords = "【候选热词库】：\n"
        self.prompt_prefix_rectify = "【纠错示例】：\n"
        self.prompt_prefix_input = "\n请纠正以下用户输入，仅输出纠正后的文本：\n"

    def build(self, user_content: str, hotwords: List[Tuple[str, float]] = None, rectify_matches: List[Tuple[str, str, float]] = None) -> List[Dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        context_parts = []
        if hotwords:
            words = [hw for hw, _ in hotwords]
            context_parts.append(f"{self.prompt_prefix_hotwords}[{', '.join(words)}]")
        if rectify_matches:
            lines = [self.prompt_prefix_rectify]
            for wrong, right, _ in rectify_matches:
                lines.append(f"- {wrong} => {right}")
            context_parts.append("\n".join(lines))
        context_str = "\n\n".join(context_parts)
        full_user_content = f"{context_str}{self.prompt_prefix_input}{user_content}"
        messages.append({"role": "user", "content": full_user_content})
        return messages

def ollama_chat(messages: List[Dict], model: str = "gemma3:4b", stream: bool = True):
    url = "http://localhost:11434/api/chat"
    payload = {"model": model, "messages": messages, "stream": stream}
    try:
        response = requests.post(url, json=payload, stream=stream)
        if not stream:
            return response.json().get('message', {}).get('content', '')
        full_res = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                content = chunk.get('message', {}).get('content', '')
                full_res += content
                print(content, end="", flush=True)
                if chunk.get('done'): break
        print()
        return full_res
    except Exception as e:
        print(f"\n[Error calling Ollama]: {e}")
        return ""

# =============================================================================
# 7. 执行展示逻辑
# =============================================================================

def main():
    # --- A. 数据准备 ---
    hotwords_data = """
    Claude
    Bilibili
    Microsoft
    买当劳
    肯德基
    # 这是一个注释
    VsCode
    VsCodes
    """
    
    rectify_data = """
# 纠错历史演示
把那个锯子给我
把那个句子给我
---
cloud code is good
Claude Code is good
---
今天天其不错
今天天气不错
"""

    test_cases_text = """
我想去吃买当劳和肯得鸡
Hello klaude
喜欢刷Bili Bili
请把那个锯子发给我一下
今天天及真的很好
I think klaud code is very good
"""
    cases = [l.strip() for l in test_cases_text.strip().split('\n') if l.strip()]

    # --- B. 系统初始化与数据加载 ---
    # 初始化纠错器和检索器
    corrector = PhonemeCorrector(threshold=0.8)
    rectifier = RectificationRAG(threshold=0.5)

    # 从字符串加载热词
    corrector.update_hotwords(hotwords_data)
    rectifier.load_rectify_text(rectify_data)

    # 从文本文件加载热词
    # corrector.load_hotwords_file("hot.txt")
    # rectifier.load_rectify_file("hot-rectify.txt")

    # --- C. 执行综合纠错演示 ---
    print("\n" + "="*50)
    print("【 CapsWriter-Offline 综合纠错系统演示 】")
    print("="*50)

    for i, t in enumerate(cases):
        print(f"\nCase {i+1}: '{t}'")
        result = corrector.correct(t)
        print(f"  [纠错结果] {result.text}")
        if result.matchs: print(f"  [匹配热词] {result.matchs}")
        if result.similars: print(f"  [相似推荐] {result.similars}")
        rag_results = rectifier.search(t)
        if rag_results:
            print(f"  [RAG 相似历史]")
            for wrong, right, score in rag_results:
                print(f"    - '{wrong}' => '{right}' (相似度: {score:.3f})")

    # --- D. Phoneme Debug 演示 ---
    print("\n" + "="*50)
    print("【 Phoneme Debug 调试演示 】")
    print("="*50)
    test_pair("cloud", "claude")
    test_pair("vscode", "VS Code")
    test_pair("七福路", "七浦路")

    # --- E. LLM 纠错演示 (Prompt 组建) ---
    print("\n" + "="*50)
    print("【 LLM 纠错演示 (Prompt 构建) 】")
    print("="*50)
    builder = PromptBuilder()
    case_idx = 0 # 使用第一个 Case
    case_text = cases[case_idx]
    result = corrector.correct(case_text)
    rag_matches = rectifier.search(case_text)
    prompt_msgs = builder.build(case_text, hotwords=result.similars, rectify_matches=rag_matches)
    print("组装后的 Prompt (Messages):")
    print(json.dumps(prompt_msgs, ensure_ascii=False, indent=2))

    print("\n[Ollama 调用测试 (默认跳过，若本地已启动 Ollama 可手动启用)]")
    # ollama_chat(prompt_msgs)

    # --- F. 性能测试 ---
    print("\n" + "="*50)
    print("【 性能测试 (FastRAG) 】")
    print("="*50)
    test_text = "我想去吃买当劳和肯得鸡, Hello klaude, 喜欢刷Bili Bili"
    in_phs = get_phoneme_info(test_text)
    if HAS_NUMBA:
        for _ in range(5): _ = corrector.fast_rag.search(in_phs)
    start = time.time(); iterations = 1000
    for _ in range(iterations): _ = corrector.fast_rag.search(in_phs)
    elapsed = time.time() - start
    print(f"测试文本: {test_text[:40]}...")
    print(f"测试轮数: {iterations}")
    print(f"平均耗时: {elapsed/iterations*1000:.3f}ms")
    print(f"吞吐量: {iterations/elapsed:.1f} 次/秒")
    print("="*50)

if __name__ == "__main__":
    main()
