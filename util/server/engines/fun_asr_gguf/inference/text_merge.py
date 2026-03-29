"""
FunASR-GGUF 结果合并模块

处理长音频识别时多个片段结果的拼接和去重。
"""

from typing import List, Dict, Any, Tuple
from . import logger

import difflib

def merge_transcription_results(
    results: List[Dict[str, Any]], 
    segment_offsets: List[float], 
    overlap_s: float
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    高度鲁棒的合并算法，使用 SequenceMatcher 寻找重叠区对齐点
    """
    if not results:
        return "", []
    
    if len(results) == 1:
        offset = segment_offsets[0]
        full_segments = []
        for seg in results[0].get('segments') or []:
            full_segments.append([seg[0], seg[1] + offset])
        return results[0]['text'], full_segments

    full_segments = []
    puncs = set("，。！？；,.!?; ")
    
    for i, res in enumerate(results):
        offset = segment_offsets[i]
        curr_segments = res.get('segments') or []

        if i == 0:
            full_segments.extend([[s[0], s[1] + offset] for s in curr_segments])
            continue

        if not curr_segments:
            continue

        # --- 寻找对齐点 ---
        # 提取 buffer 末尾和新片段开头
        # 我们关注全局时间戳在 [offset - 1.0, ...] 之间的部分
        buffer_overlap_segs = [s for s in full_segments if s[1] >= offset - 1.0]
        buffer_overlap_text = "".join([s[0] for s in buffer_overlap_segs])
        
        # 提取新片段的前部分作为匹配源
        curr_overlap_limit = overlap_s + 1.0
        curr_overlap_segs = [s for s in curr_segments if s[1] <= curr_overlap_limit]
        curr_overlap_text = "".join([s[0] for s in curr_overlap_segs])
        
        # 使用 SequenceMatcher 寻找最佳对齐
        sm = difflib.SequenceMatcher(None, buffer_overlap_text, curr_overlap_text)
        match = sm.find_longest_match(0, len(buffer_overlap_text), 0, len(curr_overlap_text))
        
        if match.size >= 2: # 至少匹配上 2 个字符
            # match.a 是 buffer_overlap_text 中的对齐点
            # match.b 是 curr_overlap_text 中的对齐点
            
            # a. 截断 buffer
            # buffer_overlap_segs[match.a] 对应的全局索引
            target_seg = buffer_overlap_segs[match.a]
            
            # 找到 target_seg 在 full_segments 中的索引 (从后往前找最接近的一个)
            try:
                global_idx = -1
                for idx in range(len(full_segments)-1, -1, -1):
                    if full_segments[idx][1] == target_seg[1] and full_segments[idx][0] == target_seg[0]:
                        global_idx = idx
                        break
                
                if global_idx != -1:
                    full_segments = full_segments[:global_idx]
            except:
                pass
            
            # b. 添加新片段从 match.b 开始的内容
            # match.b 是 curr_overlap_text 中的索引，对应 curr_overlap_segs
            # 我们需要找到它在 curr_segments 中的原始索引
            match_idx_in_curr = -1
            match_seg = curr_overlap_segs[match.b]
            for idx, s in enumerate(curr_segments):
                if s is match_seg: # 对象级别匹配最准确
                    match_idx_in_curr = idx
                    break
            
            if match_idx_in_curr != -1:
                to_add = curr_segments[match_idx_in_curr:]
                full_segments.extend([[s[0], s[1] + offset] for s in to_add])
            else:
                # 几乎不可能
                full_segments.extend([[s[0], s[1] + offset] for s in curr_segments])
        else:
            # 兜底：基于时间戳硬拼接
            last_time = full_segments[-1][1] if full_segments else offset
            to_add = [s for s in curr_segments if s[1] + offset > last_time + 0.1]
            full_segments.extend([[s[0], s[1] + offset] for s in to_add])

    # 后处理：清理标点重复和残留
    clean_segments = []
    for s in full_segments:
        if clean_segments and s[0] in puncs and clean_segments[-1][0] == s[0]:
            continue
        clean_segments.append(s)

    full_text = "".join([s[0] for s in clean_segments])
    return full_text, clean_segments
