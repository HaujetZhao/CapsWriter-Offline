"""
SRT 字幕生成与处理工具
"""

import os
from datetime import timedelta
from typing import List, Dict, Any
import srt

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
    
    # 标点符号分句参考
    puncs = set("，。！？；, .!?;")
    
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
        is_punc = char in puncs
        is_last = (i == len(segments) - 1)
        too_long = len(current_chars) >= max_chars_per_line
        
        if is_punc or is_last or too_long:
            end_time = time_s + 0.5 # 默认标点/结尾给 0.5s 停顿展示
            # 如果下一条已经开始了，则以前面为准
            if not is_last and segments[i+1]['start'] < end_time:
                end_time = segments[i+1]['start']
            
            content = "".join(current_chars).strip()
            # 移除内容末尾的标点符号
            content = content.rstrip("，。！？；, .!?;")
            
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
