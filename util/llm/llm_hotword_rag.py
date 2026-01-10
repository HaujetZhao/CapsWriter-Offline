"""
LLM 热词 RAG 检索

基于音素的热词检索，参考 FunASR 的 phoneme_tokenizer 实现
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
from util.logger import get_logger

logger = get_logger('client')

try:
    from pypinyin import pinyin, Style
    from pypinyin.style._utils import get_finals, get_initials
except ImportError:
    logger.warning("pypinyin 未安装，热词音素匹配功能不可用。运行 'pip install pypinyin' 安装。")
    pinyin = None
    Style = None
    get_finals = None
    get_initials = None


def split_mixed_label(input_str: str) -> List[str]:
    """
    将中英文混合字符串切分为 token 列表
    """
    tokens = []
    s = input_str.lower()
    while len(s) > 0:
        # 匹配连续的英文字符或标点
        match = re.match(r'[a-z!?,<>()\']+', s)
        if match is not None:
            word = match.group(0)
        else:
            # 否则取单个字符（通常是中文）
            word = s[0:1]
        tokens.append(word)
        s = s[1:] if match is None else s[len(word):]
        s = s.strip(' ')
    return tokens


def get_phoneme_seq(text: str) -> List[str]:
    """
    将文本转换为音素序列

    对于中文字符：转换为 [声母, 韵母, 声调]
    对于英文/符号：保持原样

    示例：
        "天" (tian1) -> ['t', 'ian', '1']
        "我" (wo3)   -> ['w', 'o', '3']
        "hello"     -> ['hello']
    """
    if not pinyin:
        return split_mixed_label(text)

    tokens = split_mixed_label(text)
    phoneme_seq = []

    for token in tokens:
        # 英文单词或符号直接保留
        if len(token) > 1:
            phoneme_seq.append(token)
            continue

        # 英文字符或数字直接保留
        if re.match(r'[a-zA-Z0-9!?,<>()\']', token):
             phoneme_seq.append(token)
             continue

        # 中文转拼音
        try:
            py_list = pinyin(token, style=Style.TONE3)

            if py_list:
                py = py_list[0][0]

                # 提取声调
                tone = ''
                if py and py[-1].isdigit():
                    tone = py[-1]
                    py_without_tone = py[:-1]
                else:
                    py_without_tone = py
                    tone = '0'

                # 提取声母和韵母
                initial = get_initials(py_without_tone, strict=False)
                final = get_finals(py_without_tone, strict=False)

                if not initial and not final:
                    phoneme_seq.append(token)
                else:
                    if initial:
                        phoneme_seq.append(initial)
                    if final:
                        phoneme_seq.append(final)
                    if tone:
                        phoneme_seq.append(tone)
            else:
                phoneme_seq.append(token)
        except Exception as e:
            phoneme_seq.append(token)

    return phoneme_seq


def fuzzy_substring_distance(main_seq: List[str], sub_seq: List[str]) -> int:
    """
    计算子序列在主序列中的最小编辑距离（允许子序列匹配主序列的任意部分）
    使用滚动数组优化的动态规划实现

    空间复杂度 O(n)，n 是子序列长度
    """
    n = len(sub_seq)
    m = len(main_seq)
    if n == 0:
        return 0
    if m == 0:
        return n

    prev = [0] * (m + 1)
    curr = [0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = i

        for j in range(1, m + 1):
            if sub_seq[i-1] == main_seq[j-1]:
                cost = 0
            else:
                cost = 1

            curr[j] = min(
                prev[j] + 1,
                curr[j-1] + 1,
                prev[j-1] + cost
            )

        prev, curr = curr, prev

    return min(prev)


class LLMHotwordRAG:
    """LLM 热词检索器"""

    def __init__(self, hotwords_file: str = 'hot_llm.txt', verbose: bool = False):
        """
        初始化热词检索器

        Args:
            hotwords_file: 热词文件路径
            verbose: 是否打印初始化信息
        """
        self.hotwords_file = Path(hotwords_file)
        self.verbose = verbose
        self.hotwords = []
        self.hotword_phonemes = {}

        self.load_hotwords()

    def load_hotwords(self):
        """加载热词列表"""
        if not self.hotwords_file.exists():
            logger.debug(f"热词文件不存在: {self.hotwords_file}")
            return

        try:
            with open(self.hotwords_file, 'r', encoding='utf-8') as f:
                # 读取非空行、非注释行
                lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]

            self.hotwords = lines
            logger.debug(f"已加载 {len(self.hotwords)} 个热词")

            # 预计算音素序列
            if self.hotwords:
                import time
                start = time.time()

                self.hotword_phonemes = {}
                for hw in self.hotwords:
                    if hw:
                        self.hotword_phonemes[hw] = get_phoneme_seq(hw)

                logger.debug(f"预计算音素完成，耗时 {time.time() - start:.2f} 秒")

        except Exception as e:
            logger.error(f"热词加载失败: {e}")

    def search(self, text: str, top_k: int = 10, threshold: float = 0.4) -> List[Tuple[str, float]]:
        """
        检索相关热词

        Args:
            text: 输入文本
            top_k: 返回前 K 个结果
            threshold: 相似度阈值 (0-1)

        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        if not self.hotwords:
            logger.debug("热词列表为空")
            return []

        text_seq = get_phoneme_seq(text)
        if not text_seq:
            logger.debug("文本音素序列为空")
            return []

        logger.debug(f"热词检索: 输入='{text}', 音素={text_seq}, 热词数={len(self.hotwords)}")

        scored_hotwords = []

        for hw, hw_seq in self.hotword_phonemes.items():
            if not hw_seq:
                continue

            # 计算编辑距离
            min_dist = fuzzy_substring_distance(text_seq, hw_seq)
            denom = len(hw_seq) if len(hw_seq) > 0 else 1
            score = 1.0 - (min_dist / denom)

            if score >= threshold:
                scored_hotwords.append((hw, round(score, 3)))

        # 按分数降序排序
        scored_hotwords.sort(key=lambda x: x[1], reverse=True)
        result = scored_hotwords[:top_k]

        if result:
            logger.debug(f"热词匹配结果: {[(hw, f'{s:.3f}') for hw, s in result]}")
        else:
            logger.debug(f"未匹配到热词（阈值={threshold}）")

        return result

    def format_hotwords_prompt(self, hotwords: List[Tuple[str, float]]) -> str:
        """
        将检索结果格式化为 prompt

        Args:
            hotwords: [(hotword, score), ...]

        Returns:
            格式化的提示字符串
        """
        if not hotwords:
            return ""

        # 提取热词（只保留词，不保留分数）
        hotword_list = [hw for hw, _ in hotwords]
        return f"热词列表：[{', '.join(hotword_list)}]"


# ======================================================================
# --- 热词检索器封装（原 llm_rag.py）---


class HotwordsRAG:
    """热词检索器 - LLMHotwordRAG 的高层封装"""

    def __init__(self, hotwords_file: str = 'hot-llm.txt'):
        from util.llm.llm_constants import RAGConstants
        self._rag = LLMHotwordRAG(hotwords_file, verbose=False)
        self._constants = RAGConstants
        from threading import Lock
        self._lock = Lock()

    def load_hotwords(self):
        """加载热词列表"""
        with self._lock:
            self._rag.load_hotwords()

    def search(self, text: str, top_k: int = None) -> List[Tuple[str, float]]:
        """
        从热词中搜索相关词汇

        Args:
            text: 输入文本
            top_k: 返回前 k 个热词，默认使用配置值

        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        if top_k is None:
            top_k = self._constants.DEFAULT_TOP_K

        with self._lock:
            return self._rag.search(text, top_k=top_k, threshold=self._constants.DEFAULT_THRESHOLD)

    def format_prompt(self, text: str) -> str:
        """
        生成热词提示

        Args:
            text: 输入文本

        Returns:
            格式化的提示字符串，如果没有相关热词则返回空字符串
        """
        hotwords = self.search(text)

        logger.debug(f"热词匹配 - 输入: '{text}'")
        if hotwords:
            logger.debug(f"热词匹配 - 命中 {len(hotwords)} 个: {[hw for hw, _ in hotwords]}")

        prompt = self._rag.format_hotwords_prompt(hotwords)
        return prompt

