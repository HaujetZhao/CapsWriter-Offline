# coding: utf-8
"""
音素处理算法

提供文本到音素序列的转换功能。
"""

import re
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

try:
    from pypinyin import pinyin, Style
    from pypinyin.style._utils import get_finals, get_initials
except ImportError:
    # 延迟警告，或者只在调用时报错
    pinyin = None
    Style = None
    get_finals = None
    get_initials = None


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


def get_phoneme_seq(text: str, ascii_split_char: bool = False) -> List[str]:
    """
    将文本转换为音素序列

    Args:
        text: 输入文本
        ascii_split_char: 是否将英文和数字拆分为单字符 (用于模糊匹配)
                       True: "Python" -> ['p', 'y', 't', 'h', 'o', 'n']
                       False: "Python" -> ['python']

    对于中文字符：转换为 [声母, 韵母, 声调]
    """
    # 规范化文本：移除符号和空格，统一处理
    normalized = normalize_text(text)
    
    if not pinyin:
        logger.warning("pypinyin 未安装，热词/纠错功能将降级为字符匹配。运行 'pip install pypinyin' 安装。")
        return split_mixed_label(normalized)

    tokens = split_mixed_label(normalized)
    phoneme_seq = []

    for token in tokens:
        # 英文单词或符号
        # re.match(r'[a-z0-9]', token) 在 normalized 后全是小写
        # split_mixed_label 已经把连续英文切成一个 token，连续数字切成一个 token
        
        is_en_num = bool(re.match(r'^[a-z0-9]+$', token))
        
        if is_en_num:
            if ascii_split_char:
                # 拆分为单字符
                phoneme_seq.extend(list(token))
            else:
                # 保持整体
                phoneme_seq.append(token)
            continue
            
        # 符号 (split_mixed_label 可能会把符号单独切出来，或者 normalized 已经移除了大部分符号)
        # 这里的 token 如果不是英文/数字，可能是中文或者剩余的标点
        
        if len(token) > 1 and not is_en_num:
            # 理论上 split_mixed_label 不会产生非英文数字的 多字符 token (除非是未识别的)
            # 但为了安全，保留
            phoneme_seq.append(token)
            continue
            
        if not token.strip():
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


def get_phoneme_info(text: str) -> Tuple[List[str], List[int]]:
    """
    获取音素序列及其对应的字符索引

    Returns:
        (phonemes, char_indices)
        phonemes: 扁平化的音素列表
        char_indices: 每个音素对应在原文本中的字符索引
    """
    # 规范化文本
    normalized = normalize_text(text)
    
    if not pinyin:
        # 降级模式：按字符切分
        tokens = split_mixed_label(normalized)
        return [], []

    tokens = split_mixed_label(normalized)
    phoneme_seq = []
    char_indices = []
    
    # 手动遍历规范化后的字符串以获取索引
    s = normalized
    idx = 0
    while idx < len(s):
        char = s[idx]
        
        # 跳过空格
        if char.isspace():
            idx += 1
            continue
            
        # 匹配英文单词或数字
        if re.match(r'[a-z0-9]', char):
            end = idx + 1
            while end < len(s) and re.match(r'[a-z0-9]', s[end]):
                end += 1
            token = s[idx:end]
            phoneme_seq.append(token)
            char_indices.append((idx, end))
            idx = end
            continue
            
        # 中文或其他字符
        token = char
        # 中文转拼音
        try:
            py_list = pinyin(token, style=Style.TONE3)
            if py_list:
                py = py_list[0][0]
                # 分解声韵调
                items = []
                tone = ''
                if py and py[-1].isdigit():
                    tone = py[-1]
                    py_without_tone = py[:-1]
                else:
                    py_without_tone = py
                    tone = '0'
                
                initial = get_initials(py_without_tone, strict=False)
                final = get_finals(py_without_tone, strict=False)

                if not initial and not final:
                    items.append(token)
                else:
                    if initial: items.append(initial)
                    if final: items.append(final)
                    if tone: items.append(tone)
                
                phoneme_seq.extend(items)
                char_indices.extend([(idx, idx+1)] * len(items))
            else:
                phoneme_seq.append(token)
                char_indices.append((idx, idx+1))
        except:
            phoneme_seq.append(token)
            char_indices.append((idx, idx+1))
            
        idx += 1
        
    return phoneme_seq, char_indices


if __name__ == "__main__":
    # Setup logging
    import sys
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

