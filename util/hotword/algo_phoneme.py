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
        logger.warning("pypinyin 未安装，热词/纠错功能将降级为字符匹配。运行 'pip install pypinyin' 安装。")
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


def get_phoneme_info(text: str) -> Tuple[List[str], List[int]]:
    """
    获取音素序列及其对应的字符索引

    Returns:
        (phonemes, char_indices)
        phonemes: 扁平化的音素列表
        char_indices: 每个音素对应在原文本中的字符索引
    """
    if not pinyin:
        # 降级模式：按字符切分
        tokens = split_mixed_label(text)
        return [], []

    tokens = split_mixed_label(text)
    phoneme_seq = []
    char_indices = []
    
    # 手动遍历原字符串以获取索引
    s = text.lower()
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
            while end < len(s) and re.match(r'[a-z0-9!?,<>()\']', s[end]):
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

