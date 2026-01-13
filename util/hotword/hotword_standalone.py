# coding: utf-8
"""
CapsWriter-Offline 独立热词与纠错系统 (Portable Standalone)
整合了最新的音素处理、相似度算法、FastRAG 加速检索和纠错历史 RAG。
"""

import sys
import os
import re
import time
import json
import requests
import threading
import logging
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
    pinyin = None
    Style = None

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
# 1. 核心模型与音素处理 (algo_phoneme)
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
    result = []; prev_char = ''
    for char in text:
        if char.isalnum() or '\u4e00' <= char <= '\u9fff':
            if char.isupper() and prev_char.islower(): result.append(' ')
            elif char.isdigit() and prev_char.isalpha(): result.append(' ')
            elif char.isalpha() and prev_char.isdigit(): result.append(' ')
            result.append(char.lower()); prev_char = char
        else:
            if result and result[-1] != ' ': result.append(' ')
            prev_char = ''
    return ''.join(result).strip()


def split_mixed_label(input_str: str) -> List[str]:
    tokens = []; s = input_str.lower()
    while len(s) > 0:
        if s[0] == ' ': s = s[1:]; continue
        match = re.match(r'[a-z]+', s)
        if match: tokens.append(match.group(0)); s = s[len(match.group(0)):]
        else:
            match = re.match(r'[0-9]+', s)
            if match: tokens.append(match.group(0)); s = s[len(match.group(0)):]
            else: tokens.append(s[0]); s = s[1:]
    return tokens


def get_phoneme_seq(text: str) -> List[Phoneme]:
    normalized = normalize_text(text)
    seq = []
    for token in split_mixed_label(normalized):
        if re.match(r'^[a-z0-9]+$', token):
            lang = 'num' if token.isdigit() else 'en'
            seq.append(Phoneme(token, lang, is_word_start=True, is_word_end=True))
        elif len(token) == 1:
            if not pinyin: seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
            else:
                try:
                    pi = pinyin(token, style=Style.INITIALS, strict=False)
                    pf = pinyin(token, style=Style.FINALS, strict=False)
                    pt = pinyin(token, style=Style.TONE3, neutral_tone_with_five=True)
                    has_init = pi and pi[0] and pi[0][0]
                    if has_init: seq.append(Phoneme(pi[0][0], 'zh', is_word_start=True))
                    if pf and pf[0] and pf[0][0]: seq.append(Phoneme(pf[0][0], 'zh', is_word_start=not has_init))
                    tone = pt[0][0][-1] if pt[0][0][-1].isdigit() else '5'
                    seq.append(Phoneme(tone, 'zh', is_word_end=True))
                except: seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
        else: seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
    return seq


def get_phoneme_info(text: str, split_char: bool = True) -> List[Phoneme]:
    if not pinyin: return [Phoneme(c, 'zh', char_start=i, char_end=i+1) for i, c in enumerate(text)]
    seq = []; pos = 0
    while pos < len(text):
        char = text[pos]
        if '\u4e00' <= char <= '\u9fff':
            zh_start = pos; scan_pos = pos + 1
            while scan_pos < len(text) and '\u4e00' <= text[scan_pos] <= '\u9fff': scan_pos += 1
            zh_end = scan_pos; fragment = text[zh_start:zh_end]
            try:
                py_initials = pinyin(fragment, style=Style.INITIALS, strict=False)
                py_finals = pinyin(fragment, style=Style.FINALS, strict=False)
                py_tones = pinyin(fragment, style=Style.TONE3, neutral_tone_with_five=True)
                min_len = min(len(fragment), len(py_initials), len(py_finals), len(py_tones))
                for i in range(min_len):
                    idx = zh_start + i; init, fin, tone = py_initials[i][0], py_finals[i][0], py_tones[i][0]
                    items = []
                    if init: items.append(Phoneme(init, 'zh', is_word_start=True, char_start=idx, char_end=idx+1))
                    if fin: items.append(Phoneme(fin, 'zh', is_word_start=not init, char_start=idx, char_end=idx+1))
                    if tone and tone[-1].isdigit(): items.append(Phoneme(tone[-1], 'zh', is_word_end=True, char_start=idx, char_end=idx+1))
                    if not items: items.append(Phoneme(fragment[i], 'zh', is_word_start=True, is_word_end=True, char_start=idx, char_end=idx+1))
                    seq.extend(items)
            except:
                for i, c in enumerate(fragment): seq.append(Phoneme(c, 'zh', is_word_start=True, is_word_end=True, char_start=zh_start+i, char_end=zh_start+i+1))
            pos = zh_end
        elif 'a' <= char.lower() <= 'z' or '0' <= char <= '9':
            st = pos; pos += 1
            while pos < len(text):
                c = text[pos]
                if not ('a' <= c.lower() <= 'z' or '0' <= c <= '9'): break
                if (text[pos-1].islower() and c.isupper()) or (text[pos-1].isalpha() and c.isdigit()) or (text[pos-1].isdigit() and c.isalpha()): break
                pos += 1
            tk = text[st:pos].lower(); lang = 'num' if tk.isdigit() else 'en'
            if split_char:
                for i, c in enumerate(tk): seq.append(Phoneme(c, lang, is_word_start=(i==0), is_word_end=(i==len(tk)-1), char_start=st+i, char_end=st+i+1))
            else: seq.append(Phoneme(tk, lang, is_word_start=True, is_word_end=True, char_start=st, char_end=pos))
        else: pos += 1
    return seq


# =============================================================================
# 2. 相似度算法 (algo_calc)
# =============================================================================

SIMILAR_PHONEMES = [{'an', 'ang'}, {'en', 'eng'}, {'in', 'ing'}, {'ian', 'iang'}, {'uan', 'uang'}, {'z', 'zh'}, {'c', 'ch'}, {'s', 'sh'}, {'l', 'n'}, {'f', 'h'}, {'ai', 'ei'}]

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

def fuzzy_substring_distance(hw_info: List[Tuple], input_info: List[Tuple]) -> float:
    n, m = len(hw_info), len(input_info)
    if n == 0: return 0.0
    if m == 0: return float(n)
    prev = [0.0] * (m + 1); curr = [0.0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = float(i)
        for j in range(1, m + 1):
            cost = _get_tuple_cost(hw_info[i-1], input_info[j-1])
            curr[j] = min(prev[j] + 1.0, curr[j-1] + 1.0, prev[j-1] + cost)
        prev, curr = curr, prev
    return min(prev)

def fuzzy_substring_score(hw_info: List[Tuple], input_info: List[Tuple]) -> float:
    n = len(hw_info)
    if n == 0: return 0.0
    return max(0.0, 1.0 - (fuzzy_substring_distance(hw_info, input_info) / n))

def fuzzy_substring_search_constrained(hw_info: List[Tuple], input_info: List[Tuple], threshold: float = 0.6) -> List[Tuple[float, int, int]]:
    n, m = len(hw_info), len(input_info)
    if n == 0 or m == 0: return []
    dp = [[float('inf')] * (m + 1) for _ in range(n + 1)]
    path = [[(0, 0)] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        if j == 0 or (j < m and input_info[j][2]): dp[0][j] = 0.0; path[0][j] = (0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = _get_tuple_cost(hw_info[i-1], input_info[j-1])
            dist_match = dp[i-1][j-1] + cost
            dist_del = dp[i-1][j] + 1.0
            dist_ins = dp[i][j-1] + 1.0
            min_dist = min(dist_match, dist_del, dist_ins)
            dp[i][j] = min_dist
            if min_dist == dist_match: path[i][j] = path[i-1][j-1]
            elif min_dist == dist_del: path[i][j] = path[i-1][j]
            else: path[i][j] = path[i][j-1]
    results = []
    for j in range(1, m + 1):
        if not input_info[j-1][3]: continue
        dist = dp[n][j]
        if dist >= n * 0.8: continue
        score = 1.0 - (dist / n)
        if score >= threshold: results.append((score, path[n][j][1], j))
    results.sort(key=lambda x: x[0], reverse=True)
    used_ends = {}
    for score, s, e in results:
        if e not in used_ends or score > used_ends[e][0]: used_ends[e] = (score, s, e)
    return sorted(used_ends.values(), key=lambda x: x[0], reverse=True)


# =============================================================================
# 3. RAG 加速检索 (rag_fast)
# =============================================================================

if HAS_NUMBA and HAS_NUMPY:
    @njit(cache=True)
    def _fuzzy_substring_numba(main_codes: np.ndarray, sub_codes: np.ndarray) -> float:
        n, m = len(sub_codes), len(main_codes)
        if n == 0 or m == 0: return float(n)
        dp = np.zeros((n + 1, m + 1), dtype=np.float32)
        for i in range(1, n + 1): dp[i, 0] = float(i)
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = 0.0 if sub_codes[i-1] == main_codes[j-1] else 1.0
                dp[i, j] = min(dp[i-1, j] + 1.0, dp[i, j-1] + 1.0, dp[i-1, j-1] + cost)
        return float(np.min(dp[n, 1:]))

class FastRAG:
    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.ph_to_code = {}; self.next_code = 1
        self.index = defaultdict(list); self.hotword_count = 0
    def _encode(self, p: str) -> int:
        if p not in self.ph_to_code: self.ph_to_code[p] = self.next_code; self.next_code += 1
        return self.ph_to_code[p]
    def _encode_seq(self, phs: List[str]) -> np.ndarray:
        return np.array([self._encode(p) for p in phs], dtype=np.int32) if HAS_NUMPY else [self._encode(p) for p in phs]
    def add_hotwords(self, hotwords: Dict[str, List[Phoneme]]):
        for hw, phs in hotwords.items():
            if not phs: continue
            codes = self._encode_seq([p.value for p in phs])
            indices = [0]
            if phs[0].lang == 'en': indices = list(range(min(len(codes), 2)))
            for i in indices: self.index[codes[i]].append((hw, codes))
            self.hotword_count += 1
    def search(self, input_phs: List[Phoneme], top_k: int = 10) -> List[Tuple[str, float]]:
        if not input_phs: return []
        input_codes = self._encode_seq([p.value for p in input_phs]); unique = set(input_codes)
        candidates = []
        seen = set()
        for c in unique:
            for hw, codes in self.index.get(c, []):
                if hw not in seen: candidates.append((hw, codes)); seen.add(hw)
        results = []
        for hw, h_codes in candidates:
            if len(h_codes) > len(input_codes) + 3: continue
            if HAS_NUMBA and HAS_NUMPY: dist = _fuzzy_substring_numba(input_codes, h_codes)
            else: dist = self._python_dist(input_codes, h_codes)
            score = 1.0 - (dist / len(h_codes))
            if score >= self.threshold: results.append((hw, round(score, 3)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    def _python_dist(self, main, sub):
        n, m = len(sub), len(main)
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1): dp[i][0] = float(i)
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = 0.0 if sub[i-1] == main[j-1] else 1.0
                dp[i][j] = min(dp[i-1][j] + 1.0, dp[i][j-1] + 1.0, dp[i-1][j-1] + cost)
        return min(dp[n][1:])


# =============================================================================
# 4. 纠错系统逻辑 (hot_phoneme & hot_rectification)
# =============================================================================

class MatchResult(NamedTuple):
    start: int; end: int; score: float; hotword: str

class CorrectionResult(NamedTuple):
    text: str; matchs: List[Tuple[str, str, float]]; similars: List[Tuple[str, str, float]]

class PhonemeCorrector:
    def __init__(self, threshold: float = 0.7, similar_threshold: float = None):
        self.threshold = threshold
        self.similar_threshold = similar_threshold if similar_threshold is not None else threshold - 0.2
        self.hotwords: Dict[str, List[Phoneme]] = {}
        self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
        self._lock = threading.Lock()
    def update_hotwords(self, text: str) -> int:
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('#')]
        new_hw = {}
        for hw in lines:
            phs = get_phoneme_info(hw)
            if phs: new_hw[hw] = phs
        with self._lock:
            self.hotwords = new_hw
            self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
            self.fast_rag.add_hotwords(new_hw)
        return len(new_hw)
    def load_hotwords_file(self, path: str) -> int:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: return self.update_hotwords(f.read())
        return 0
    def _find_matches(self, text, fast_results, input_processed):
        matches, similars = [], []
        search_thresh = min(self.threshold, self.similar_threshold) - 0.1
        for hw, _ in fast_results:
            hw_phs = self.hotwords[hw]; hw_compare = [p.info[:5] for p in hw_phs]
            found = fuzzy_substring_search_constrained(hw_compare, input_processed, threshold=search_thresh)
            for score, s_idx, e_idx in found:
                char_st, char_ed = input_processed[s_idx][5], input_processed[e_idx-1][6]
                res = MatchResult(char_st, char_ed, score, hw)
                if score >= self.threshold: matches.append(res)
                if score >= self.similar_threshold: similars.append((text[char_st:char_ed], hw, score))
        similars.sort(key=lambda x: (x[2], len(x[1])), reverse=True)
        final_sims, seen = [], set()
        for o, hw, s in similars:
            if hw not in seen: final_sims.append((o, hw, s)); seen.add(hw)
        return matches, final_sims
    def _resolve_and_replace(self, text, matches):
        matches.sort(key=lambda x: (x.score, x.end - x.start), reverse=True)
        final_m, occupied = [], []
        for m in matches:
            if any(not (m.end <= rs or m.start >= re) for rs, re in occupied): continue
            if text[m.start:m.end] != m.hotword: final_m.append(m)
            occupied.append((m.start, m.end))
        res = list(text); final_m.sort(key=lambda x: x.start, reverse=True)
        for m in final_m: res[m.start:m.end] = list(m.hotword)
        return "".join(res), [(text[m.start:m.end], m.hotword, m.score) for m in sorted(final_m, key=lambda x: x.start)]
    def correct(self, text, k=10):
        in_phs = get_phoneme_info(text)
        if not in_phs or not self.hotwords: return CorrectionResult(text, [], [])
        with self._lock:
            fast_res = self.fast_rag.search(in_phs, top_k=100); processed = [p.info for p in in_phs]
            matches, sims = self._find_matches(text, fast_res, processed)
        nt, fhw = self._resolve_and_replace(text, matches)
        return CorrectionResult(nt, fhw, sims[:k])

def _get_word_boundaries(text: str) -> List[Tuple[int, int, str]]:
    bounds, i, n = [], 0, len(text)
    while i < n:
        if not (text[i].isalnum() or '\u4e00' <= text[i] <= '\u9fff'): i += 1; continue
        s = i
        if '\u4e00' <= text[i] <= '\u9fff': i += 1
        else:
            low = text[i].islower()
            while i < n and text[i].isalnum():
                if text[i].isupper() and low and i > s: break
                low = text[i].islower(); i += 1
        bounds.append((s, i, text[s:i]))
    return bounds

def extract_diff_fragments(wrong: str, right: str) -> List[str]:
    wb, rb = _get_word_boundaries(wrong), _get_word_boundaries(right)
    matcher = SequenceMatcher(None, [b[2] for b in wb], [b[2] for b in rb]); frags = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ('replace', 'delete') and i2 > i1: frags.append(wrong[wb[i1][0]:wb[i2-1][1]])
        if tag in ('replace', 'insert') and j2 > j1: frags.append(right[rb[j1][0]:rb[j2-1][1]])
    return list(dict.fromkeys(frags))

class RectificationRAG:
    def __init__(self, threshold=0.5):
        self.threshold = threshold; self.records = []; self._lock = threading.Lock()
    def load_rectify_text(self, text):
        recs = []
        for block in text.split('---'):
            lines = [l.strip() for l in block.split('\n') if l.strip() and not l.strip().startswith('#')]
            if len(lines) >= 2:
                w, r = lines[0], lines[1]; frags = extract_diff_fragments(w, r) or [w]
                recs.append({'wrong': w, 'right': r, 'fphs': {f: [p.info[:5] for p in get_phoneme_seq(f)] for f in frags}})
        with self._lock: self.records = recs
    def load_rectify_file(self, path: str):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: self.load_rectify_text(f.read())
    def search(self, text, top_k=5):
        in_phs = [p.info[:5] for p in get_phoneme_seq(text)]; matches = []
        with self._lock:
            for rec in self.records:
                best = 0.0
                for fphs in rec['fphs'].values():
                    if not fphs: continue
                    score = fuzzy_substring_score(fphs, in_phs)
                    if score > best: best = score
                if best >= self.threshold: matches.append((rec['wrong'], rec['right'], round(best, 3)))
        return sorted(matches, key=lambda x: x[2], reverse=True)[:top_k]


# =============================================================================
# 5. 调试工具 (Phoneme Debug)
# =============================================================================

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
    return 1.0 - (min_dist / n), best_start, end_pos

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


# =============================================================================
# 6. LLM 集成 (Prompt Builder & Ollama Client)
# =============================================================================

class PromptBuilder:
    def __init__(self, system_prompt: str = "你是一个输入法纠错助手。"):
        self.system_prompt = system_prompt
        self.prompt_prefix_hotwords = "热词列表："
        self.prompt_prefix_rectify = "纠错历史：\n"
        self.prompt_prefix_input = "用户输入："

    def build(self, user_content: str, hotwords: List[Tuple[str, float]] = None, rectify_matches: List[Tuple[str, str, float]] = None) -> List[Dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        context_parts = []
        if hotwords:
            words = [hw for hw, _, _ in hotwords]
            context_parts.append(f"{self.prompt_prefix_hotwords}[{', '.join(words)}]")
        if rectify_matches:
            lines = [self.prompt_prefix_rectify]
            for wrong, right, _ in rectify_matches: lines.append(f"- {wrong} => {right}")
            context_parts.append("\n".join(lines))
        context_str = "\n\n".join(context_parts)
        full_user_content = f"{context_str}\n\n{self.prompt_prefix_input}{user_content}"
        messages.append({"role": "user", "content": full_user_content})
        return messages

def ollama_chat(messages: List[Dict], model: str = "gemma3:4b", stream: bool = True):
    url = "http://localhost:11434/api/chat"
    payload = {"model": model, "messages": messages, "stream": stream}
    try:
        response = requests.post(url, json=payload, stream=stream)
        if not stream: return response.json().get('message', {}).get('content', '')
        full_res = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                content = chunk.get('message', {}).get('content', '')
                full_res += content; print(content, end="", flush=True)
                if chunk.get('done'): break
        print(); return full_res
    except Exception as e:
        print(f"\n[Error calling Ollama]: {e}"); return ""


# =============================================================================
# 7. 数据准备与主流演示
# =============================================================================

# --- A. 数据准备 ---
hotwords_data = """
Claude
Bilibili
Microsoft
麦当劳
肯德基
VsCode
七浦路
"""

rectify_data = """
把那个锯子给我
把那个句子给我
---
cloud code is good
Claude Code is good
"""

cases = [
    "我想去吃买当劳和肯得鸡",
    "喜欢刷Bili Bili",
    "请把那个锯子发给我一下",
    "我很喜欢 cloud",
    "西安是一个好地方",
    "我刚才先了一下"
]

# --- B. 系统初始化 ---
corrector = PhonemeCorrector(threshold=0.8)
rectifier = RectificationRAG(threshold=0.5)

# 加载演示数据 (也可通过 load_hotwords_file / load_rectify_file 加载外部文件)
corrector.update_hotwords(hotwords_data)
rectifier.load_rectify_text(rectify_data)

# 尝试加载外部文件 (如果存在)
corrector.load_hotwords_file("hot.txt")
rectifier.load_rectify_file("hot-rectify.txt")

# --- C. 执行综合纠错演示 ---
print("\n" + "="*50)
print("【 CapsWriter-Offline 综合纠错系统演示 】")
print("="*50)

for i, t in enumerate(cases):
    print(f"\n\nCase {i+1}: '{t}'")
    result = corrector.correct(t)
    print(f"  [纠错结果] {result.text}")
    if result.matchs: 
        print(f"  [匹配热词]")
        print("\n".join([f"    - ({score:.3f}) {wrong} => {right} " for wrong, right, score in result.matchs]))
    if result.similars: 
        print(f"  [潜在热词]")
        print("\n".join([f"    - ({score:.3f}) {wrong} => {right} " for wrong, right, score in result.similars]))
    rag_results = rectifier.search(t)
    if rag_results:
        print(f"  [历史纠错]")
        print("\n".join([f"    - ({score:.3f}) {wrong} => {right} " for wrong, right, score in rag_results]))

# --- D. 音素匹配调试演示 ---
print("\n" + "="*50)
print("【 Phoneme Debug 调试演示 】")
print("="*50)
test_pair("cloud", "claude")
test_pair("vscode", "VS Code")
test_pair("七福路", "七浦路")

# --- E. LLM Prompt 组建与调用演示 ---
print("\n" + "="*50)
print("【 LLM 纠错演示 (Prompt 构建) 】")
print("="*50)
builder = PromptBuilder()
case_text = "我很喜欢 cloud"
result = corrector.correct(case_text)
rag_matches = rectifier.search(case_text)
prompt_msgs = builder.build(case_text, hotwords=result.similars, rectify_matches=rag_matches)

print("组装后的 Prompt (Messages):")
print(json.dumps(prompt_msgs, ensure_ascii=False, indent=2))

# 如果 Ollama 在运行，可以取消下面注释进行真实测试
# ollama_chat(prompt_msgs)

# --- F. 性能测试 (FastRAG) ---
print("\n" + "="*50)
print("【 性能测试 (FastRAG) 】")
print("="*50)
if HAS_NUMBA:
    print(f"Numba: Enabled")
    # 预热
    _ = corrector.fast_rag.search(get_phoneme_info("hello"), top_k=1)
    
    start = time.time()
    for _ in range(100):
        _ = corrector.fast_rag.search(get_phoneme_info("这是一段用于测试检索速度的长文本，看看能跑多快"), top_k=5)
    elapsed = time.time() - start
    print(f"100 次长文本检索耗时: {elapsed:.4f}s (约 {100/elapsed:.1f} 次/秒)")
else:
    print("Numba: Disabled (Speed will be much lower)")
