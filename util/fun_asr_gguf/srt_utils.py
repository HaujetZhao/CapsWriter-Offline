"""
SRT 字幕生成与处理工具
"""

import os
from datetime import timedelta
from typing import List, Dict, Any
import srt
from util.constants import Punctuation

def generate_srt_file(
    segments: List[Dict[str, Any]], 
    output_path: str,
    max_chars_per_line: int = 30
):
    """
    根据字级时间戳生成 SRT 文件
    
    Args:
        segments: 列表，每项包含 {'char', 'start'}
        output_path: 导出路径
        max_chars_per_line: 每行最大字符数
    """
    if not segments:
        return

    subtitles = []
    
    # 分句参考
    puncs = set(Punctuation.ALL + " ")
    pause_threshold = 0.4      # 停顿超过 0.4s 则考虑切分
    min_chars_to_break = 5    # 至少积累了 5 个字才允许因为停顿而切分
    long_pause_threshold = 1.0 # 如果停顿超过 1.0s，则无视字数强制切分
    
    current_chars = []
    start_time = segments[0]['start']
    
    for i, seg in enumerate(segments):
        char = seg['char']
        time_s = seg['start']
        
        current_chars.append(char)
        
        # 判断是否需要切分：
        # 1. 遇到标点
        # 2. 达到最大长度
        # 3. 最后一个字符
        # 4. 检测到长停顿 (当前字与下一个字之间)
        
        is_punc = char in puncs
        is_last = (i == len(segments) - 1)
        too_long = len(current_chars) >= max_chars_per_line
        
        # 停顿检测
        has_pause = False
        if not is_last:
            pause_duration = segments[i+1]['start'] - time_s
            # 只有在积累了一定字数后，才响应普通停顿；或者是超长停顿强制响应
            if (len(current_chars) >= min_chars_to_break and pause_duration > pause_threshold) \
               or (pause_duration > long_pause_threshold):
                has_pause = True
        
        if is_punc or is_last or too_long or has_pause:
            # 确定结束时间
            if is_last:
                end_time = time_s + 0.5
            else:
                next_start = segments[i+1]['start']
                end_time = min(time_s + 0.5, (time_s + next_start) / 2)

            content = "".join(current_chars).strip()
            # 移除内容末尾的标点符号，让字幕更干净
            content = content.rstrip(Punctuation.ALL + " ")
            
            if content:
                subtitles.append(srt.Subtitle(
                    index=len(subtitles) + 1,
                    start=timedelta(seconds=start_time),
                    end=timedelta(seconds=end_time),
                    content=content
                ))
            
            # 重置
            if not is_last:
                current_chars = []
                start_time = segments[i+1]['start']

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subtitles))

    return output_path

