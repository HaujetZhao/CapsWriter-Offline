import numpy as np

class ResultIntegrator:
    @staticmethod
    def integrate(greedy_results, detected_hotwords):
        """
        [核心算法] 将 Greedy 识别流与热词匹配流进行无缝融合与替换

        算法分两步：
          1. 预处理：过滤掉与前一个热词时间重叠的热词（保留最早出现的）
          2. 双指针合并：遍历 greedy token，热词指针只向前推进，O(N+M)

        Args:
            greedy_results:    List[dict] -> [{'text': '...', 'timestamp': ...}, ...]
            detected_hotwords: List[dict] -> [{'text': '...', 'timestamp': ..., 'end': ..., 'tokens': [...]}, ...]
        Returns:
            final_results: List[dict]
        """
        # --- 步骤 1：过滤重叠热词，保留时间最早的那个 ---
        # 两个热词重叠的判定：后一个的 timestamp < 前一个的 end
        detected_hotwords.sort(key=lambda x: x["timestamp"])
        active_hotwords = []
        last_end = -1.0
        for hw in detected_hotwords:
            if hw["timestamp"] >= last_end - 0.02:   # 不重叠，保留
                active_hotwords.append(hw)
                last_end = hw["end"]
            # 否则与前一个重叠，丢弃

        # --- 步骤 2：双指针合并 ---
        final_results = []
        hw_idx = 0          # 指向当前"候选热词"
        emitted = set()     # 记录已输出的热词索引（按位置去重，防止一个热词被输出多次）

        for g in greedy_results:
            g_timestamp = g["timestamp"]

            # 推进热词指针：跳过已完全结束的热词
            while hw_idx < len(active_hotwords) and active_hotwords[hw_idx]["end"] + 0.02 < g_timestamp:
                hw_idx += 1

            # 判断当前 greedy token 是否落在热词区间内
            in_hotword_span = False
            if hw_idx < len(active_hotwords):
                hw = active_hotwords[hw_idx]
                # 0.02s 冗余处理浮点偏移和 CTC 发散
                if hw["timestamp"] - 0.02 <= g_timestamp <= hw["end"] + 0.02:
                    in_hotword_span = True
                    if hw_idx not in emitted:
                        # 首次进入该热词区间：输出热词块
                        final_results.extend(ResultIntegrator._merge_tokens_to_chunks(hw))
                        emitted.add(hw_idx)
                    # 无论是否首次，当前 greedy token 都跳过（已被热词覆盖）

            if not in_hotword_span:
                final_results.append({
                    "text": g["text"],
                    "timestamp": g_timestamp,
                    "is_hotword": False
                })

        return final_results

    @staticmethod
    def _merge_tokens_to_chunks(hw):
        """
        将热词内部的 Token 和原始文本进行“块对齐”切分
        """
        origin_text = hw["text"]
        search_base = origin_text.lower()
        chunks = []
        
        # 1. 寻找每个 Token 覆盖的字符起始位置
        anchors = [] # (idx_in_text, timestamp)
        curr_search_pos = 0
        for tk in hw["tokens"]:
            clean_tk = tk["token"].replace("\u2581", "").strip().lower()
            if not clean_tk: continue
            idx = search_base.find(clean_tk, curr_search_pos)
            if idx != -1:
                anchors.append((idx, tk["time"]))
                curr_search_pos = idx + len(clean_tk)
        
        if not anchors: 
            anchors.append((0, hw["timestamp"]))
        elif anchors[0][0] != 0:
            anchors.insert(0, (0, hw["timestamp"]))
            
        # 2. 根据锚点切割原始文本块
        for i in range(len(anchors)):
            start_idx, start_time = anchors[i]
            next_idx = anchors[i+1][0] if (i+1) < len(anchors) else len(origin_text)
            
            chunk_text = origin_text[start_idx:next_idx]
            chunks.append({
                "text": chunk_text,
                "timestamp": start_time,
                "is_hotword": True
            })
        return chunks
