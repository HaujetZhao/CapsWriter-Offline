# coding=utf-8
import re
from datetime import timedelta
from typing import List, Optional
import srt
import json
from .schema import TranscriptionResult, RecognitionResult
from .chinese_itn import chinese_to_num as itn

def results_to_srt(items: List[RecognitionResult], max_chars: int = 40) -> str:
    """
    将 RecognitionResult 列表转换为 SRT 格式内容。
    按逗号、句号、问号、感叹号以及换行符进行分行。
    """
    if not items:
        return ""

    subtitles = []
    current_texts = []
    start_time = None
    
    # 匹配分割符号：中文全角标点、英文半角标点、以及可能存在的换行符
    split_pattern = re.compile(r'[，。？！、\n]|[,.?!]\s*')
    
    for i, item in enumerate(items):
        if start_time is None:
            start_time = item.start
        
        current_texts.append(item.text)
        current_content = "".join(current_texts)
        
        # 触发分割的条件：存在标点或超过最大字数
        if split_pattern.search(item.text) or len(current_content) >= max_chars:
            content = current_content.strip()
            if content:
                # 移除末尾标点用于 ITN 处理（可选，保持原样也行）
                clean_content = content.rstrip("，。？！、,.?!")
                itn_content = itn(clean_content)
                
                # 预测结束时间
                end_time_val = items[i+1].start if (i+1) < len(items) else item.start + 0.5
                
                subtitles.append(srt.Subtitle(
                    index=len(subtitles) + 1,
                    start=timedelta(seconds=start_time),
                    end=timedelta(seconds=end_time_val),
                    content=itn_content
                ))
            current_texts = []
            start_time = None
            
    # 处理剩余文本
    if current_texts:
        content = "".join(current_texts).strip()
        if content:
            itn_content = itn(content.rstrip("，。？！：、,.?!"))
            end_time_val = items[-1].start + 0.5
            subtitles.append(srt.Subtitle(
                index=len(subtitles) + 1,
                start=timedelta(seconds=start_time),
                end=timedelta(seconds=end_time_val),
                content=itn_content
            ))
            
    return srt.compose(subtitles)

def export_to_srt(path: str, result: TranscriptionResult):
    """将转录结果保存为 SRT 文件"""
    if not result.results:
        with open(path, "w", encoding="utf-8") as f: f.write("")
        return
    
    content = results_to_srt(result.results)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 已生成字幕文件: {path}")

def export_to_json(path: str, result: TranscriptionResult):
    """将转录结果保存为 JSON 格式的时间戳列表"""
    data = [
        {
            "text": r.text,
            "start": round(r.start, 3),
            "is_hotword": r.is_hotword
        }
        for r in result.results
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已导出时间戳: {path}")

def export_to_txt(path: str, result: TranscriptionResult):
    """将转录结果保存为普通文本"""
    final_text = itn(result.text)
    # 按标点换行
    formatted_text = re.sub(r'([，。？！：])', r'\1\n', final_text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(formatted_text)
    print(f"✅ 已保存文本文件: {path}")
