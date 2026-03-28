import re
import numpy as np
import time

class HotwordTrieNode:
    def __init__(self):
        self.children = {}
        self.word_indices = [] # 记录在此节点结束的热词索引

class HotwordRadar:
    """
    [Trie 树加速版] 高性能热词召回组件
    
    优化核心：
    1. 字符级 Trie 树：合并所有热词的前缀，CapsWriter 和 CapsWriter-Offline 只需搜索一次前缀。
    2. 全局状态记忆化：缓存 (frame, trie_node)，消除重复路径搜索。
    3. 极速剪枝：基于 Trie 节点的子节点字典，快速过滤 Top-K 中无关的 Token。
    """
    def __init__(self, hotwords, tokenizer):
        self.tokenizer = tokenizer
        
        # 1. 预计算全量词表的小写映射
        self.vocab_lower = []
        for i in range(tokenizer.get_piece_size()):
            piece = tokenizer.id_to_piece(i)
            self.vocab_lower.append(piece.lower().replace('\u2581', '').strip())
        
        # 2. 初始化热词
        self.update_hotwords(hotwords)

    def update_hotwords(self, hotwords):
        """动态更新热词列表并重构 Trie 树"""
        self.hotwords = hotwords
        self.trie = HotwordTrieNode()
        self.search_hotwords = [re.sub(r'[^\w\s]+', ' ', w) for w in hotwords]
        self.hotword_lower_strings = []
        
        for idx, sw in enumerate(self.search_hotwords):
            clean = re.sub(r'\s+', '', sw).lower()
            self.hotword_lower_strings.append(clean)
            if not clean: continue
            
            # 插入 Trie
            node = self.trie
            for char in clean:
                if char not in node.children:
                    node.children[char] = HotwordTrieNode()
                node = node.children[char]
            node.word_indices.append(idx)

    def scan(self, full_ids, full_probs, top_k=5, blank_id=0, max_lookahead=15, verbose=False):
        """
        [Trie 树加速版] 高性能热词扫描
        - topk_ids: (T, 100) 原始模型输出
        - topk_probs: (T, 100) 原始模型输出
        - top_k: 雷达实际搜索的深度
        """
        t_scan_start = time.perf_counter()
        
        # 内部下放 Top-K 切片逻辑
        if top_k is not None:
            full_ids = full_ids[:, :top_k]
            full_probs = full_probs[:, :top_k]
            
        # 从 Top-K 空间的第 0 列提取 Top-1 (Greedy 非空帧判断基准)
        top1_indices = full_ids[:, 0]
            
        T, K = full_ids.shape
        hits = []

        for t in range(T):
            if top1_indices[t] == blank_id:
                continue
            
            t_frame_start = time.perf_counter()
            
            # 触发：检查当前帧 Top-K 中有哪些 Token 是 Trie 的根起始
            seen_tokens = set()
            for k in range(K):
                tid = int(full_ids[t, k])
                tc = self.vocab_lower[tid]
                if not tc or tc in seen_tokens: continue
                seen_tokens.add(tc)
                
                # 如果 Token 首字符在 Trie 根部，启动批量 DFS
                if tc[0] in self.trie.children:
                    # 获取首 Piece 的词边界标记
                    original_piece = self.tokenizer.id_to_piece(tid)
                    has_boundary = original_piece.startswith('\u2581')
                    
                    # 尝试消耗此 Token 在 Trie 上的路径
                    node = self.trie
                    match_possible = True
                    for char in tc:
                        if char in node.children:
                            node = node.children[char]
                        else:
                            match_possible = False
                            break
                    
                    if match_possible:
                        # 启动集中式 DFS，从 node 节点继续往后找
                        frame_hits = self._dfs_trie(
                            t, k, node, full_ids, full_probs, top1_indices, 
                            blank_id, max_lookahead, {}, verbose=verbose
                        )
                        for h in frame_hits:
                            h["has_word_boundary"] = has_boundary
                            hits.append(h)

            t_frame_end = time.perf_counter()
            if verbose and (t_frame_end - t_frame_start) > 0.0001: # 仅打印有实际计算的帧
                print(f"[Radar Profile] 帧 {t:3d} 匹配耗时: {(t_frame_end - t_frame_start)*1000:7.3f} ms")

        t_scan_total = (time.perf_counter() - t_scan_start) * 1000

        if verbose: print(f"[Radar Profile] 扫描总耗时: {t_scan_total:.3f} ms")

        return self._post_process(hits, top1_indices, blank_id)

    def _dfs_trie(self, t_curr, k_curr, start_node, topk_ids, topk_probs, top1_indices, blank_id, max_lookahead, memo, verbose=False):
        """
        基于 Trie 树的深度优先集中搜索
        memo: (frame_idx, node_id) -> Dict[word_idx: best_match_from_here]
        """
        T, K = topk_ids.shape
        p_start = float(topk_probs[t_curr, k_curr])
        t1 = self.vocab_lower[topk_ids[t_curr, k_curr]]
        
        # 定义内部递归
        def search(f_prev, node):
            state = (f_prev, id(node))
            if state in memo: return memo[state]
            
            # 使用字典存储：word_idx -> 该节点往后能找到的最佳完成路径
            # 这样对于同一个 Trie 节点，同样的词只需要保留概率最高的一个分支
            best_results = {}
            
            # A. 检查当前节点是否是热词终点
            for w_idx in node.word_indices:
                res = {
                    "word_idx": w_idx,
                    "end_frame": f_prev,
                    "prob_sum": 0.0, # 这里的 prob_sum 只存后续的，t_curr 在最外层加
                    "count": 0,
                    "frame_indices": [],
                    "matched_tokens": []
                }
                best_results[w_idx] = res
                if verbose:
                    print(f"      [Match End] Word: {self.hotwords[w_idx]:<15} | Path: {t1} + {' '.join(res['matched_tokens'])}")
            
            # B. 继续往后搜索
            search_end = min(f_prev + 1 + max_lookahead, T)
            for f in range(f_prev + 1, search_end):
                if f > f_prev + 1 and np.any(top1_indices[f_prev+1:f] != blank_id):
                    break
                
                for k in range(K):
                    tc = self.vocab_lower[topk_ids[f, k]]
                    if not tc: continue
                    
                    temp_node = node
                    match_ok = True
                    for char in tc:
                        if char in temp_node.children:
                            temp_node = temp_node.children[char]
                        else:
                            match_ok = False
                            break
                    
                    if match_ok:
                        sub_matches = search(f, temp_node)
                        if sub_matches:
                            p_curr = float(topk_probs[f, k])
                            for w_idx, sr in sub_matches.items():
                                new_prob_sum = sr["prob_sum"] + p_curr
                                new_count = sr["count"] + 1
                                avg_prob = new_prob_sum / new_count
                                
                                # 更新在该 (f_prev, node) 下，到达 w_idx 的最优后缀
                                if w_idx not in best_results or avg_prob > (best_results[w_idx]["prob_sum"] / max(1, best_results[w_idx]["count"])):
                                    best_results[w_idx] = {
                                        "word_idx": w_idx,
                                        "end_frame": sr["end_frame"],
                                        "prob_sum": new_prob_sum,
                                        "count": new_count,
                                        "frame_indices": [f] + sr["frame_indices"],
                                        "matched_tokens": [tc] + sr["matched_tokens"]
                                    }

            memo[state] = best_results
            return best_results

        # 启动递归
        all_best_suffixes = search(t_curr, start_node)
        
        # 组装最终结果
        final_matches = []
        for w_idx, sr in all_best_suffixes.items():
            final_matches.append({
                "word_idx": w_idx,
                "start_frame": t_curr,
                "end_frame": sr["end_frame"],
                "prob": (sr["prob_sum"] + p_start) / (sr["count"] + 1),
                "frame_indices": [t_curr] + sr["frame_indices"],
                "matched_tokens": [t1] + sr["matched_tokens"]
            })
        return final_matches


    def _post_process(self, hits, top1_indices, blank_id):
        if not hits: return []
        
        # 1. 基础过滤与质量评估
        filtered = []
        for h in hits:
            # nb_greedy: 路径中落点在 Greedy (Top-1) 非空帧的数量 (模型主线支撑点越多越真实)
            nb_greedy = sum(1 for f in h["frame_indices"] if top1_indices[f] != blank_id)
            # b_greedy: 路径中落点在 Greedy 空帧上的数量 (穿过静默区越少越真实)
            b_greedy = len(h["frame_indices"]) - nb_greedy
            
            # 基础门槛：至少要有 2 帧得到了模型 Greedy 输出的支撑（即便不是同一个字）
            if nb_greedy >= 2:
                h["nb_greedy"] = nb_greedy
                h["b_greedy"] = b_greedy
                filtered.append(h)
        
        if not filtered: return []
        
        # 2. 排序与多维优先级覆盖去重
        filtered.sort(key=lambda x: x["start_frame"])
        selected = []
        i = 0
        while i < len(filtered):
            best = filtered[i]
            j = i + 1
            while j < len(filtered) and filtered[j]["start_frame"] <= best["end_frame"]:
                candidate = filtered[j]
                
                # --- 优先级 1: Greedy 非空帧匹配的数量越多越优先 ---
                if candidate["nb_greedy"] > best["nb_greedy"]:
                    best = candidate
                elif candidate["nb_greedy"] == best["nb_greedy"]:
                    # --- 优先级 2: Greedy 空帧匹配的数量越少越优先 ---
                    if candidate["b_greedy"] < best["b_greedy"]:
                        best = candidate
                    elif candidate["b_greedy"] == best["b_greedy"]:
                        # --- 优先级 3: 原始字符长度优先 (保留最大匹配原则) ---
                        len_c = len(self.hotword_lower_strings[candidate["word_idx"]])
                        len_b = len(self.hotword_lower_strings[best["word_idx"]])
                        if len_c > len_b:
                            best = candidate
                        elif len_c == len_b:
                            # --- 优先级 4: 平均概率优先 ---
                            if candidate["prob"] > best["prob"]:
                                best = candidate
                j += 1
            selected.append(best)
            i = j
            
        # 3. 格式化输出
        final = []
        for h in selected:
            text = self.hotwords[h["word_idx"]]
            if h.get("has_word_boundary", False):
                text = " " + text
            
            final.append({
                "text": text,
                "timestamp": round(h["start_frame"] * 0.060, 3),
                "end": round(h["end_frame"] * 0.060, 3),
                "prob": round(h["prob"], 4),
                "tokens": [{"token": t, "time": round(f*0.060, 3)} 
                           for t, f in zip(h["matched_tokens"], h["frame_indices"])]
            })
        return final

