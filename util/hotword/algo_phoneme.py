# coding: utf-8
"""
音素处理算法

提供文本到音素序列的转换功能。
"""

import re
from typing import List, Tuple, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Phoneme:
    """
    带语言属性的音素

    Attributes:
        value: 音素值（如 'b', 'ing', 'python', '4'）
        lang: 语言类型 ('zh'=中文, 'en'=英文, 'num'=数字, 'other'=其他)
        is_word_start: 是否是字边界起始位置（声母/零声母）
        is_word_end: 是否是字边界结束位置（声调）
        char_start: 该音素在原文本中的起始索引
        char_end: 该音素在原文本中的结束索引
    """
    value: str
    lang: Literal['zh', 'en', 'num', 'other']
    is_word_start: bool = False
    is_word_end: bool = False
    char_start: int = 0
    char_end: int = 0

    @property
    def is_tone(self) -> bool:
        """是否是声调"""
        return self.value.isdigit()

    @property
    def is_english(self) -> bool:
        """是否是英文"""
        return self.lang == 'en'

    @property
    def info(self) -> Tuple[str, str, bool, bool, bool, int, int]:
        """返回包含所有属性的七元组 (值, 语言, 起始标, 结束标, 是否声调, 字始, 字终)"""
        return (self.value, self.lang, self.is_word_start, self.is_word_end, self.is_tone, self.char_start, self.char_end)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Phoneme({self.value}, {self.lang}, start={self.is_word_start}, end={self.is_word_end})"

try:
    from pypinyin import pinyin, Style
except ImportError:
    # 延迟警告，或者只在调用时报错
    pinyin = None
    Style = None


def normalize_text(text: str) -> str:
    """
    规范化文本：驼峰拆分 + 分隔符替换为空格 + 统一小写
    
    这确保：
    - `CapsWriter` -> `caps writer`
    - `iPhone15Pro` -> `iphone 15 pro`
    - `7-Zip` / `7 zip` -> `7 zip`
    """
    result = []
    prev_char = ''
    
    for char in text:
        if char.isalnum() or '\u4e00' <= char <= '\u9fff':
            # 驼峰拆分：在大写字母前插入空格（如果前一个是小写字母）
            if char.isupper() and prev_char.islower():
                result.append(' ')
            # 数字边界：字母和数字之间插入空格
            elif char.isdigit() and prev_char.isalpha():
                result.append(' ')
            elif char.isalpha() and prev_char.isdigit():
                result.append(' ')
            
            result.append(char.lower())
            prev_char = char
        else:
            # 非字母数字中文字符替换为空格（作为分隔符）
            if result and result[-1] != ' ':
                result.append(' ')
            prev_char = ''
    
    return ''.join(result).strip()


def split_mixed_label(input_str: str) -> List[str]:
    """
    将中英文混合字符串切分为 token 列表
    
    规则：
    - 英文单词作为一个 token
    - 数字作为单独的 token
    - 中文每个字单独处理
    
    示例：
    - "hello world" -> ['hello', 'world']
    - "iphone15" -> ['iphone', '15']
    - "7zip" -> ['7', 'zip']
    - "测试123" -> ['测', '试', '123']
    """
    tokens = []
    s = input_str.lower()
    
    while len(s) > 0:
        # 跳过空格
        if s[0] == ' ':
            s = s[1:]
            continue
            
        # 匹配连续的英文字母
        match = re.match(r'[a-z]+', s)
        if match:
            tokens.append(match.group(0))
            s = s[len(match.group(0)):]
            continue
            
        # 匹配连续的数字
        match = re.match(r'[0-9]+', s)
        if match:
            tokens.append(match.group(0))
            s = s[len(match.group(0)):]
            continue
            
        # 其他字符（中文等）单独处理
        tokens.append(s[0])
        s = s[1:]
    
    return tokens


def get_phoneme_seq(text: str, ascii_split_char: bool = False) -> List[Phoneme]:
    """
    将文本转换为音素序列（带语言属性）

    Args:
        text: 输入文本
        ascii_split_char: 是否将英文和数字拆分为单字符 (用于模糊匹配)
                       True: "Python" -> [Phoneme('p','en'), ..., Phoneme('n','en')]
                       False: "Python" -> [Phoneme('python','en')]

    对于中文字符：转换为 [声母, 韵母, 声调]，语言类型为 'zh'
    对于英文单词：语言类型为 'en'
    对于数字：语言类型为 'num'

    Returns:
        List[Phoneme]: 带语言属性的音素列表
    """
    # 规范化文本：移除符号和空格，统一处理
    normalized = normalize_text(text)

    if not pinyin:
        logger.warning("pypinyin 未安装，热词/纠错功能将降级为字符匹配。运行 'pip install pypinyin' 安装。")
        # 降级模式：返回字符序列，语言类型统一设为 'zh'，每个字符都是独立的字
        return [Phoneme(c, 'zh', is_word_start=True, is_word_end=True) for c in split_mixed_label(normalized)]

    tokens = split_mixed_label(normalized)
    phoneme_seq: List[Phoneme] = []

    for token in tokens:
        # 英文单词或数字
        is_en_num = bool(re.match(r'^[a-z0-9]+$', token))

        if is_en_num:
            lang: Literal['en', 'num'] = 'num' if token.isdigit() else 'en'
            if ascii_split_char:
                # 拆分为单字符（每个字符都是独立的字）
                phoneme_seq.extend([Phoneme(c, lang, is_word_start=True, is_word_end=True) for c in token])
            else:
                # 保持整体（整个单词是一个字）
                phoneme_seq.append(Phoneme(token, lang, is_word_start=True, is_word_end=True))
            continue

        # 符号或其他非英文数字的多字符 token
        if len(token) > 1 and not is_en_num:
            phoneme_seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
            continue

        if not token.strip():
            continue

        # 中文转拼音
        try:
            # 直接使用 pypinyin 的 Style 获取声母、韵母、声调
            py_initials = pinyin(token, style=Style.INITIALS, strict=False)
            py_finals = pinyin(token, style=Style.FINALS, strict=False)
            py_tone3 = pinyin(token, style=Style.TONE3, strict=False)

            if py_tone3 and py_tone3[0] and py_tone3[0][0]:
                # 判断是否零声母（没有声母）
                has_initial = py_initials and py_initials[0] and py_initials[0][0]

                # 提取声母（字起始）
                if has_initial:
                    initial = py_initials[0][0]
                    if initial:
                        phoneme_seq.append(Phoneme(initial, 'zh', is_word_start=True))

                # 提取韵母（零声母时是字起始）
                if py_finals and py_finals[0] and py_finals[0][0]:
                    final = py_finals[0][0]
                    if final:
                        is_start = not has_initial  # 零声母时韵母是字起始
                        phoneme_seq.append(Phoneme(final, 'zh', is_word_start=is_start))

                # 提取声调（字结束）
                py = py_tone3[0][0]
                tone = ''
                if py and py[-1].isdigit():
                    tone = py[-1]
                else:
                    tone = '0'

                if tone:
                    phoneme_seq.append(Phoneme(tone, 'zh', is_word_end=True))

                # 如果没有提取到任何音素，保留原字
                if not any([
                    has_initial,
                    (py_finals and py_finals[0] and py_finals[0][0]),
                ]):
                    phoneme_seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
            else:
                phoneme_seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))
        except Exception as e:
            phoneme_seq.append(Phoneme(token, 'zh', is_word_start=True, is_word_end=True))

    return phoneme_seq


def get_phoneme_info(text: str, ascii_split_char: bool = True) -> List[Phoneme]:
    """
    获取带位置和语言属性的音素序列（高层编排）
    """
    if not pinyin:
        return [Phoneme(c, 'zh', char_start=i, char_end=i+1) for i, c in enumerate(text)]

    phoneme_seq: List[Phoneme] = []
    pos = 0
    while pos < len(text):
        char = text[pos]

        # 1. 判定类型
        if '\u4e00' <= char <= '\u9fff':
            # 处理中文片段
            pos = _process_zh(text, pos, phoneme_seq)
        elif char.isalnum():
            # 处理英文/数字片段
            pos = _process_en_num(text, pos, phoneme_seq, ascii_split_char)
        else:
            # 其他字符（空格、标点）：跳过，保持音素流连续以便匹配
            pos += 1
            
    return phoneme_seq


def _process_zh(text: str, pos: int, seq: List[Phoneme]) -> int:
    """处理连续的中文片段，并返回扫描后的新位置"""
    zh_start = pos
    scan_pos = pos + 1
    while scan_pos < len(text) and '\u4e00' <= text[scan_pos] <= '\u9fff':
        scan_pos += 1
    zh_end = scan_pos
    fragment = text[zh_start:zh_end]
    
    try:
        py_initials = pinyin(fragment, style=Style.INITIALS, strict=False, errors='ignore')
        py_finals = pinyin(fragment, style=Style.FINALS, strict=False, errors='ignore')
        py_tones = pinyin(fragment, style=Style.TONE3, neutral_tone_with_five=True, errors='ignore')

        min_len = min(len(fragment), len(py_initials), len(py_finals), len(py_tones))
        for i in range(min_len):
            idx = zh_start + i
            init, fin, tone = py_initials[i][0], py_finals[i][0], py_tones[i][0]
            
            items = []
            if init:
                items.append(Phoneme(init, 'zh', is_word_start=True, char_start=idx, char_end=idx+1))
            if fin:
                items.append(Phoneme(fin, 'zh', is_word_start=not init, char_start=idx, char_end=idx+1))
            if tone and tone[-1].isdigit():
                items.append(Phoneme(tone[-1], 'zh', is_word_end=True, char_start=idx, char_end=idx+1))
                
            if not items:
                items.append(Phoneme(fragment[i], 'zh', is_word_start=True, is_word_end=True, char_start=idx, char_end=idx+1))
            seq.extend(items)
    except Exception:
        # 降级处理
        for i, c in enumerate(fragment):
            seq.append(Phoneme(c, 'zh', is_word_start=True, is_word_end=True, char_start=zh_start+i, char_end=zh_start+i+1))
            
    return zh_end


def _process_en_num(text: str, pos: int, seq: List[Phoneme], split_char: bool) -> int:
    """处理英文/数字片段，支持驼峰和数字边界拆分"""
    start_pos = pos
    while pos < len(text):
        char = text[pos]
        if not char.isalnum(): break
        
        # 处理逻辑拆分边界 (驼峰 aA, 字母数字 a1, 数字字母 1a)
        if pos > start_pos:
            prev = text[pos-1]
            if (prev.islower() and char.isupper()) or \
               (prev.isalpha() and char.isdigit()) or \
               (prev.isdigit() and char.isalpha()):
                break
        pos += 1
    
    end_pos = pos
    token = text[start_pos:end_pos].lower()
    lang = 'num' if token.isdigit() else 'en'
    
    if split_char:
        for i, c in enumerate(token):
            seq.append(Phoneme(c, lang, is_word_start=(i==0), is_word_end=(i==len(token)-1), 
                               char_start=start_pos+i, char_end=start_pos+i+1))
    else:
        seq.append(Phoneme(token, lang, is_word_start=True, is_word_end=True, 
                           char_start=start_pos, char_end=end_pos))
    return end_pos


if __name__ == "__main__":
    # Setup UTF-8 output for Windows
    import sys
    import io

    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # Setup logging
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    print("\n--- algo_phoneme 测试 ---")

    test_cases = [
        "撒贝宁",
        "Hello World",
        "iPhone 15 Pro",
        "测试123",
        "西安", # xi'an
        "先",   # xian
    ]

    for text in test_cases:
        print(f"\nText: {text}")
        seq, indices = get_phoneme_info(text)
        print(f"Phonemes: {seq}")
        # print(f"Indices: {indices}")

