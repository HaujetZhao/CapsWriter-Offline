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


def lines_match_words(text_lines: List[str], words: List) -> List[srt.Subtitle]:
    """
    words[0] = {
                'start': 0.0,
                'end' : 5.0,
                'word' : 'good'
                }
    """
    # 空的字幕列表
    subtitle_list = []

    cursor = 0              # 索引，指向最新已确认的下一个
    words_num = len(words)  # 词数，结束条件
    for index, line in enumerate(text_lines):

        # 先清除空行
        if not line.strip():
            continue
        
        # 避免越界
        if cursor >= words_num:
            break

        # 初始化
        temp_text = line
        t1 = words[cursor]['start']
        t2 = words[cursor]['end']
        threshold = 8
        have_match = False

        # 开始匹配
        probe = cursor  # 重置探针
        while (not have_match) or (probe - cursor < threshold):
            if probe >= words_num:
                break  # 探针越界，结束
            w = words[probe]['word'].strip(' ,.?!，。？！@')
            t3 = words[probe]['start']
            t4 = words[probe]['end']
            probe += 1
            if w in temp_text:
                have_match = True
                temp_text = temp_text.replace(w, '', 1)
                t2 = t4  # 延长字幕结束时间
                cursor = probe
                if not temp_text:
                    break  # 如果 temp 已清空,则代表本条字幕已完

        # 新建字幕
        subtitle = srt.Subtitle(index=index,
                                content=line,
                                start=timedelta(seconds=t1),
                                end=timedelta(seconds=t2))
        subtitle_list.append(subtitle)
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
    subtitle_list = lines_match_words(text_lines, words)

    # 写入 srt
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subtitle_list))

def main(files: List[Path]):
    for file in files:
        one_task(file)
        print(f'写入完成：{file}')

if __name__ == '__main__':
    typer.run(main)
        

