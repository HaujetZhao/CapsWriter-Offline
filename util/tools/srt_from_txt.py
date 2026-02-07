"""
脚本介绍：
    用 sherpa-onnx 生成的字幕，总归是会有一些缺陷
    例如有错字，分句不准
    
    所以除了自动生成的 srt 文件
    还额外生成了 txt 文件（每行一句），和 json 文件（包含每个字的时间戳）
    
    用户可以在识别完成后，手动修改 txt 文件，更正少量的错误，正确地分行
    然后调用这个脚本，处理 txt 文件
    
    脚本会找到同文件名的 json 文件，从里面得到字级时间戳，再按照 txt 里面的分行，
    生成正确的 srt 字幕
"""


import json
from datetime import timedelta
from pathlib import Path
from typing import List, Dict, Union

import typer
import srt
from rich import print
import re 


import difflib

def lines_match_words(text_lines: List[str], words: List) -> List[srt.Subtitle]:
    """
    使用 SequenceMatcher 将分行文本与字级时间戳进行最优对齐
    
    Args:
        text_lines: 用户修改并分行后的文本列表
        words: 原始字级时间戳列表 [{'word': '字', 'start': 0.0, 'end': 0.1}, ...]
        
    Returns:
        对齐后的 srt.Subtitle 列表
    """
    raw_tokens_text = "".join([w['word'] for w in words])
    all_lines_text = "".join([line.strip() for line in text_lines])
    
    # 标点和清理模式：动态涵盖所有已知中英文标点
    from util.constants import Punctuation
    punc_pattern = re.compile(rf'[{re.escape(Punctuation.ALL)}\s\d]')
    
    # 建立 token_idx 到字符偏移的映射
    token_chars = []
    token_indices = []
    for i, w in enumerate(words):
        word_clean = punc_pattern.sub('', w['word'].lower())
        for char in word_clean:
            token_chars.append(char)
            token_indices.append(i)
    pure_tokens_text = "".join(token_chars)
    
    # 全局对齐
    clean_all_lines = punc_pattern.sub('', all_lines_text.lower())
    sm = difflib.SequenceMatcher(None, pure_tokens_text, clean_all_lines)
    matches = sm.get_matching_blocks()
    
    # 字符偏移 -> word 索引映射
    char_to_word_map = {}
    for match in matches:
        for i in range(match.size):
            char_to_word_map[match.b + i] = token_indices[match.a + i]
            
    # 映射行到时间戳
    subtitle_list = []
    current_char_offset = 0
    last_word_idx = 0
    
    for index, line in enumerate(text_lines):
        line_clean = punc_pattern.sub('', line.lower())
        if not line_clean:
            continue
            
        line_len = len(line_clean)
        found_word_indices = [
            char_to_word_map[i] 
            for i in range(current_char_offset, current_char_offset + line_len) 
            if i in char_to_word_map
        ]
        
        if found_word_indices:
            start_word_idx = min(found_word_indices)
            end_word_idx = max(found_word_indices)
            t1 = words[start_word_idx]['start']
            t2 = words[end_word_idx]['end']
            last_word_idx = end_word_idx
        else:
            t1 = words[min(last_word_idx + 1, len(words)-1)]['start']
            t2 = t1 + 0.5
            
        subtitle = srt.Subtitle(
            index=len(subtitle_list) + 1,
            content=line.strip(),
            start=timedelta(seconds=t1),
            end=timedelta(seconds=t2)
        )
        subtitle_list.append(subtitle)
        current_char_offset += line_len
        
    return subtitle_list



def get_words(json_file: Path) -> list:
    # 读取分词 json 文件
    with open(json_file, 'r', encoding='utf-8') as f:
        json_info = json.load(f)

    # 获取带有时间戳的分词列表
    words = [{'word': token.replace('@', ''), 'start': timestamp, 'end': timestamp + 0.2} 
             for (timestamp, token) in zip(json_info['timestamps'], json_info['tokens'])]
    for i in range(len(words) - 1):
        words[i]['end'] = min(words[i]['end'], words[i+1]['start'])
    
    return words


def get_lines(txt_file: Path) -> List[str]:
    # 读取分好行的字幕
    with open(txt_file, 'r', encoding='utf-8') as f:
        text_lines = f.readlines()
    return text_lines

def generate_srt_file(words: list, text_lines: List[str], srt_file: Path):
    """根据提供的 words 和 text_lines 生成 srt 文件"""
    subtitle_list = lines_match_words(text_lines, words)
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subtitle_list))

def one_task(media_file: Path):
    # 配置要打开的文件
    txt_file = media_file.with_suffix('.txt')
    json_file = media_file.with_suffix('.json')
    srt_file = media_file.with_suffix('.srt')
    if (not txt_file.exists()) or (not json_file.exists()):
        print(f'无法找到 {media_file}对应的txt、json文件，跳过')
        return None

    # 获取带有时间戳的分词列表，获取分行稿件，匹配得到 srt 
    words = get_words(json_file)
    text_lines = get_lines(txt_file)
    
    generate_srt_file(words, text_lines, srt_file)

def main(files: List[Path]):
    for file in files:
        one_task(file)
        print(f'写入完成：{file}')

if __name__ == '__main__':
    typer.run(main)
        

