import numpy as np
import re
from typing import List, Dict, Any

class CTCAligner:
    """组件：负责将 CTC 时间戳与 LLM 输出文本进行对齐"""

    @staticmethod
    def _merge_english_words(chars: List[List[Any]]) -> List[List[Any]]:
        """后处理：将连续的英文字符合并为单词，空格作为独立 token"""
        merged = []
        buf = []  # 当前累积的英文 token
        for item in chars:
            ch = item[0]
            if re.match(r'[a-zA-Z]', ch):
                buf.append(item)
            else:
                if buf:
                    word = "".join(b[0] for b in buf)
                    merged.append([word, buf[0][1]])
                    buf = []
                merged.append(item)
        if buf:
            word = "".join(b[0] for b in buf)
            merged.append([word, buf[0][1]])
        return merged

    @staticmethod
    def align(ctc_results, llm_text: str, timestamp_offset: float = 0.0) -> List[List[Any]]:
        """
        使用 Needleman-Wunsch 算法对齐 CTC 结果和 LLM 文本
        只使用起始位置进行匹配
        返回格式: [[token, timestamp], ...]，连续英文字母已合并为单词
        """
        if not ctc_results or not llm_text:
            return []

        # 1. 展开 CTC 结果为字符级别（只保留起始位置）
        ctc_chars = []
        for item in ctc_results:
            text = item.text
            timestamp = item.timestamp

            if len(text) > 0:
                # 假设每个字符占用相同时间间隔
                char_duration = 0.08  # 默认每个字符约 80ms
                for i, char in enumerate(text):
                    c_timestamp = timestamp + i * char_duration
                    ctc_chars.append({"char": char, "timestamp": c_timestamp})

        llm_chars = list(llm_text)

        n = len(ctc_chars) + 1
        m = len(llm_chars) + 1

        # Core DP Matrix
        score = np.zeros((n, m), dtype=np.float32)
        # trace: 1=diag, 2=up, 3=left
        trace = np.zeros((n, m), dtype=np.int8)

        gap_penalty = -1.0
        match_score = 1.0
        mismatch_score = -1.0

        # Init margins
        for i in range(n): score[i][0] = i * gap_penalty
        for j in range(m): score[0][j] = j * gap_penalty

        # Fill DP
        for i in range(1, n):
            for j in range(1, m):
                char_ctc = ctc_chars[i-1]["char"]
                char_llm = llm_chars[j-1]

                s_diag = score[i-1][j-1] + (match_score if char_ctc.lower() == char_llm.lower() else mismatch_score)
                s_up = score[i-1][j] + gap_penalty
                s_left = score[i][j-1] + gap_penalty

                best = max(s_diag, s_up, s_left)
                score[i][j] = best

                if best == s_diag: trace[i][j] = 1
                elif best == s_up: trace[i][j] = 2
                else: trace[i][j] = 3

        # Traceback
        llm_alignment = [None] * len(llm_chars)
        i, j = n - 1, m - 1

        while i > 0 or j > 0:
            if i > 0 and j > 0 and trace[i][j] == 1:
                llm_alignment[j-1] = ctc_chars[i-1]
                i -= 1
                j -= 1
            elif i > 0 and (j == 0 or trace[i][j] == 2):
                i -= 1
            elif j > 0 and (i == 0 or trace[i][j] == 3):
                llm_alignment[j-1] = None
                j -= 1

        # 插值填充未对齐的字符
        anchors = []
        for idx, item in enumerate(llm_alignment):
            if item is not None:
                anchors.append((idx, item["timestamp"]))

        final_chars = []

        def get_interpolated_start(target_idx):
            """插值计算起始位置"""
            prev_a, next_a = None, None
            for a in anchors:
                if a[0] < target_idx:
                    prev_a = a
                elif a[0] > target_idx:
                    next_a = a
                    break

            if prev_a and next_a:
                p_idx, p_start = prev_a
                n_idx, n_start = next_a

                # 线性插值
                total_gap = n_idx - p_idx
                time_gap = n_start - p_start
                step = time_gap / total_gap

                relative_step = target_idx - p_idx
                return p_start + relative_step * step
            elif prev_a:
                return prev_a[1] + 0.05  # 向后推一点
            elif next_a:
                return max(0, next_a[1] - 0.05)  # 向前推一点
            else:
                return 0.0

        for idx, char in enumerate(llm_chars):
            if llm_alignment[idx]:
                s = llm_alignment[idx]["timestamp"]
            else:
                s = get_interpolated_start(idx)
            
            # 应用偏移并确保不为负数
            s = max(s + timestamp_offset, 0.0)
            final_chars.append([char, s])

        return CTCAligner._merge_english_words(final_chars)
