# coding=utf-8
import re
from datetime import timedelta
from typing import List, Optional
import srt
import json
from .schema import ForcedAlignResult, ForcedAlignItem, TranscribeResult
from .chinese_itn import chinese_to_num as itn

def alignment_to_srt(items: Optional[List[ForcedAlignItem]], max_chars: int = 40) -> str:
    """
    将对齐结果转换为 SRT 格式内容。
    按逗号、句号、问号、感叹号以及换行符进行分行。
    """
    if not items:
        return ""

    subtitles = []
    current_texts = []
    start_time = None
    
    # 匹配分割符号：中文全角标点、英文半角标点、以及可能存在的换行符
    # 特别注意：在有的 ASR 引擎中，标点后可能跟有空格，也一并匹配
    split_pattern = re.compile(r'[，。？！、\n]|[,.?!]\s*')
    
    for item in items:
        # 记录每一行字幕的开始时间
        if start_time is None:
            start_time = item.start_time
        
        current_texts.append(item.text)
        
        # 聚合当前已有的文本
        current_content = "".join(current_texts)
        
        # 触发分割的条件：
        # 1. 遇到了分割标点符号
        # 2. 或者当前行字符数超过了 max_chars (防止单行过长)
        if split_pattern.search(item.text) or len(current_content) >= max_chars:
            content = current_content.strip()
            if content:
                # 移除末尾标点
                content = content.rstrip("，。？！、,.?!")
                # 应用 ITN 处理
                itn_content = itn(content)
                subtitles.append(srt.Subtitle(
                    index=len(subtitles) + 1,
                    start=timedelta(seconds=start_time),
                    end=timedelta(seconds=item.end_time),
                    content=itn_content
                ))
            current_texts = []
            start_time = None
            
    # 处理末尾残余文本
    if current_texts:
        content = "".join(current_texts).strip()
        if content:
            # 移除末尾标点
            content = content.rstrip("，。？！：、,.?!")
            # 应用 ITN 处理
            itn_content = itn(content)
            end_time = items[-1].end_time
            subtitles.append(srt.Subtitle(
                index=len(subtitles) + 1,
                start=timedelta(seconds=start_time),
                end=timedelta(seconds=end_time),
                content=itn_content
            ))
            
    return srt.compose(subtitles)

def alignment_to_json(items: Optional[List[ForcedAlignItem]]) -> List[dict]:
    """将对齐结果转换为可序列化的字典列表"""
    if not items:
        return []
    return [
        {
            "text": it.text,
            "start": round(it.start_time, 3),
            "end": round(it.end_time, 3)
        }
        for it in items
    ]

def export_to_srt(path: str, result: TranscribeResult):
    """将对齐结果保存为 SRT 文件"""
    if not result.alignment:
        with open(path, "w", encoding="utf-8") as f: f.write("")
        return
    
    content = alignment_to_srt(result.alignment.items)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 已生成字幕文件: {path}")

def export_to_json(path: str, result: TranscribeResult):
    """将对齐结果保存为 JSON 文件"""
    if not result.alignment:
        with open(path, "w", encoding="utf-8") as f: f.write("[]")
        return

    data = alignment_to_json(result.alignment.items)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已导出时间戳: {path}")

def export_to_txt(path: str, result: TranscribeResult):
    """将转录结果处理后保存为 TXT 文件 (含 ITN 和标点换行)"""
    # 1. ITN 处理
    final_text = itn(result.text)
    # 2. 按照标点符号换行，保留标点
    formatted_text = re.sub(r'([，。？！：])', r'\1\n', final_text)
    # 3. 对于英文字母后面的逗号空格、句号空格，也要换行
    formatted_text = re.sub(r'(?<=[a-zA-Z])([,\.] )', r'\1\n', formatted_text)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(formatted_text)
    print(f"✅ 已保存文本文件: {path}")
