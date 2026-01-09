"""
LLM 热词 RAG 检索

基于音素的热词检索，参考 FunASR 的 phoneme_tokenizer 实现
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional

try:
    from pypinyin import pinyin, Style
    from pypinyin.style._utils import get_finals, get_initials
except ImportError:
    print("Warning: pypinyin not found. Please install it using `pip install pypinyin`.")
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
            if self.verbose:
                print(f"[LLM 热词 RAG] 文件不存在: {self.hotwords_file}")
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

            if self.verbose and self.hotwords:
                print(f"[LLM 热词 RAG] 已加载 {len(self.hotwords)} 个热词")

            # 预计算音素序列
            if self.hotwords:
                import time
                start = time.time()

                if self.verbose:
                    print(f"[LLM 热词 RAG] 正在预计算音素...", end=' ', flush=True)

                self.hotword_phonemes = {}
                for hw in self.hotwords:
                    if hw:
                        self.hotword_phonemes[hw] = get_phoneme_seq(hw)

                if self.verbose:
                    print(f"完成 ({time.time() - start:.2f}秒)")

        except Exception as e:
            print(f"[LLM 热词 RAG] 加载失败: {e}")

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
            print("[RAG DEBUG] 热词列表为空")
            return []

        text_seq = get_phoneme_seq(text)
        if not text_seq:
            print("[RAG DEBUG] 文本音素序列为空")
            return []

        print(f"[RAG DEBUG] 输入文本: {text}")
        print(f"[RAG DEBUG] 文本音素: {text_seq}")
        print(f"[RAG DEBUG] 热词总数: {len(self.hotwords)}")
        print(f"[RAG DEBUG] 阈值: {threshold}, Top-K: {top_k}")

        scored_hotwords = []
        all_scores = []

        for hw, hw_seq in self.hotword_phonemes.items():
            if not hw_seq:
                continue

            # 计算编辑距离
            min_dist = fuzzy_substring_distance(text_seq, hw_seq)
            denom = len(hw_seq) if len(hw_seq) > 0 else 1
            score = 1.0 - (min_dist / denom)
            all_scores.append((hw, score, min_dist))

            if score >= threshold:
                scored_hotwords.append((hw, round(score, 3)))

        # 打印所有得分（用于调试）
        all_scores.sort(key=lambda x: x[1], reverse=True)
        print(f"[RAG DEBUG] 所有热词得分 (Top 10):")
        for hw, score, dist in all_scores[:10]:
            match = "✓" if score >= threshold else "✗"
            print(f"  {match} {hw:10} 得分:{score:.3f} 距离:{dist}")

        # 按分数降序排序
        scored_hotwords.sort(key=lambda x: x[1], reverse=True)
        return scored_hotwords[:top_k]

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


# 测试
if __name__ == "__main__":
    print("=" * 60)
    print("LLM 热词 RAG - 测试模式")
    print("=" * 60)

    # 创建测试热词文件
    test_file = Path("test_hot_llm.txt")
    test_file.write_text("""# 测试热词文件
周杰伦
篮球
天气
今天
不错
乒乓球
足球
""", encoding='utf-8')

    # 创建检索器
    rag = LLMHotwordRAG(str(test_file), verbose=True)

    # 测试检索
    test_cases = [
        "今天天其不错",
        "我们去打蓝球吧",
        "叫上周杰仑",
    ]

    print("\n" + "=" * 60)
    print("检索测试")
    print("=" * 60)

    for text in test_cases:
        print(f"\n输入: {text}")
        results = rag.search(text, top_k=5, threshold=0.3)
        print(f"检索结果:")
        for hw, score in results:
            print(f"  {hw:8} - 相似度: {score:.3f}")

        print(f"\nPrompt:")
        print(rag.format_hotwords_prompt(results))

    # 清理
    test_file.unlink()

    print("\n" + "=" * 60)
