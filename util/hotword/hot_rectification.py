# coding: utf-8
"""
LLM 纠错历史 RAG

检索用户自定义的纠错历史 (错句 => 正句)，作为 LLM 的背景知识。

工作原理：
1. 从 "错句 => 正句" 中提取被修改的片段（改前、改后）
2. 用这些片段作为检索词，与语音识别结果匹配
3. 返回得分最高的前 n 条完整纠错记录喂给 LLM
"""

import threading
import time
from pathlib import Path
from typing import List, Tuple, Dict, Set
from difflib import SequenceMatcher

from .algo_phoneme import get_phoneme_seq, normalize_text
from .algo_calc import fuzzy_substring_distance
from util.logger import get_logger

logger = get_logger('client')


def get_char_phoneme_count(text: str) -> int:
    """估算文本的音素数量（简化版：中文每字3音素，英文每单词1音素）"""
    count = 0
    i = 0
    while i < len(text):
        char = text[i]
        if '\u4e00' <= char <= '\u9fff':
            # 中文：每字约 3 个音素（声母+韵母+声调）
            count += 3
            i += 1
        elif char.isalpha():
            # 英文：找到完整单词，算 1 个音素
            j = i + 1
            while j < len(text) and text[j].isalpha():
                j += 1
            count += 1
            i = j
        elif char.isdigit():
            # 数字：连续数字算 1 个音素
            j = i + 1
            while j < len(text) and text[j].isdigit():
                j += 1
            count += 1
            i = j
        else:
            i += 1
    return count


def expand_fragment(text: str, start: int, end: int, min_phonemes: int = 4) -> Tuple[int, int]:
    """
    如果片段音素数量不足，向两边扩展
    
    Args:
        text: 完整文本
        start: 片段起始位置
        end: 片段结束位置
        min_phonemes: 最小音素数量
        
    Returns:
        (扩展后起始位置, 扩展后结束位置)
    """
    fragment = text[start:end]
    current_count = get_char_phoneme_count(fragment)
    
    if current_count >= min_phonemes:
        return start, end
    
    # 需要扩展的音素数量
    needed = min_phonemes - current_count
    
    # 交替向左右扩展
    new_start, new_end = start, end
    expand_left = True
    
    while needed > 0:
        if expand_left and new_start > 0:
            # 向左扩展一个"词"
            new_start -= 1
            char = text[new_start]
            
            # 如果是中文，扩展一个字
            if '\u4e00' <= char <= '\u9fff':
                needed -= 3
            # 如果是英文，找到完整单词
            elif char.isalpha():
                while new_start > 0 and text[new_start - 1].isalpha():
                    new_start -= 1
                needed -= 1
            # 如果是数字，找到完整数字
            elif char.isdigit():
                while new_start > 0 and text[new_start - 1].isdigit():
                    new_start -= 1
                needed -= 1
                
        elif not expand_left and new_end < len(text):
            # 向右扩展一个"词"
            char = text[new_end]
            
            if '\u4e00' <= char <= '\u9fff':
                new_end += 1
                needed -= 3
            elif char.isalpha():
                new_end += 1
                while new_end < len(text) and text[new_end].isalpha():
                    new_end += 1
                needed -= 1
            elif char.isdigit():
                new_end += 1
                while new_end < len(text) and text[new_end].isdigit():
                    new_end += 1
                needed -= 1
            else:
                new_end += 1
        else:
            # 一边到头了，只向另一边扩展
            if new_start == 0 and new_end < len(text):
                expand_left = False
                continue
            elif new_end == len(text) and new_start > 0:
                expand_left = True
                continue
            else:
                # 两边都到头了
                break
        
        expand_left = not expand_left
    
    return new_start, new_end


def extract_diff_fragments(wrong: str, right: str, min_phonemes: int = 4) -> List[str]:
    """
    提取两个句子之间的差异片段（包括错误版本和正确版本）
    自动扩展过短的片段以达到最小音素数量
    
    例如：
    "原锯子不对" => "原句子不对"
      差异：锯/句 (太短) -> 扩展为 原锯子/原句子
    
    "今天天气不做" => "今天天气不错"  
      差异：不做/不错 (够长)
    
    Args:
        wrong: 错误句子
        right: 正确句子
        min_phonemes: 最小音素数量，默认4（约一个中文词或英文单词）
    """
    fragments = set()
    
    # 使用 SequenceMatcher 找出差异
    matcher = SequenceMatcher(None, wrong, right)
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            # 替换：两边都是差异片段，可能需要扩展
            exp_i1, exp_i2 = expand_fragment(wrong, i1, i2, min_phonemes)
            exp_j1, exp_j2 = expand_fragment(right, j1, j2, min_phonemes)
            
            wrong_frag = wrong[exp_i1:exp_i2]
            right_frag = right[exp_j1:exp_j2]
            
            if wrong_frag:
                fragments.add(wrong_frag)
            if right_frag:
                fragments.add(right_frag)
                
        elif tag == 'delete':
            # 删除：错句中有，正句中没有
            exp_i1, exp_i2 = expand_fragment(wrong, i1, i2, min_phonemes)
            wrong_frag = wrong[exp_i1:exp_i2]
            if wrong_frag:
                fragments.add(wrong_frag)
                
        elif tag == 'insert':
            # 插入：正句中有，错句中没有
            exp_j1, exp_j2 = expand_fragment(right, j1, j2, min_phonemes)
            right_frag = right[exp_j1:exp_j2]
            if right_frag:
                fragments.add(right_frag)
    
    return list(fragments)


class RectifyRecord:
    """单条纠错记录"""
    def __init__(self, wrong: str, right: str, fragments: List[str]):
        self.wrong = wrong
        self.right = right
        self.fragments = fragments
        # 预计算每个片段的音素序列
        self.fragment_phonemes = {
            f: get_phoneme_seq(f) for f in fragments
        }
    
    def __repr__(self):
        return f"RectifyRecord('{self.wrong}' => '{self.right}', fragments={self.fragments})"


class RectificationRAG:
    """
    纠错历史 RAG 检索器

    加载 'hot-rectify.txt'，通过 RAG 检索相似的差异片段，
    返回对应的完整纠错记录作为 Prompt 上下文。

    文件格式：用 --- 分隔的多行内容
    每一段中：
    - 第一行：原始文本（错误文本）
    - 第二行：修正文本（正确文本）
    忽略以 # 开头的注释和空行
    """

    def __init__(self, rectify_file: str = 'hot-rectify.txt', threshold: float = 0.6):
        """
        初始化
        
        Args:
            rectify_file: 纠错历史文件路径
            threshold: 相似度阈值
        """
        self.rectify_file = Path(rectify_file)
        self.threshold = threshold
        self.records: List[RectifyRecord] = []
        self._lock = threading.Lock()
        
        self.load_history()
        
    def load_history(self):
        """加载纠错历史

        格式：用 --- 分隔的多行内容
        每一段中：
        - 第一行：原始文本（错误文本）
        - 第二行：修正文本（正确文本）
        忽略以 # 开头的注释和空行
        """
        if not self.rectify_file.exists():
            with open(self.rectify_file, 'w', encoding='utf-8') as f:
                f.write('# 纠错历史文件\n')
                f.write('# 格式：用 --- 分隔的多行内容\n')
                f.write('# 每一段第一行是原始文本，第二行是修正文本\n')
                f.write('# 例如：\n')
                f.write('# 原锯子\n')
                f.write('# 原句子\n')
                f.write('# ---\n')
                f.write('# caps riter\n')
                f.write('# CapsWriter\n')
            return

        try:
            with open(self.rectify_file, 'r', encoding='utf-8') as f:
                content = f.read()

            new_records = []

            # 按分隔符切分
            blocks = content.split('---')

            start_time = time.time()
            for block in blocks:
                lines = block.strip().split('\n')

                # 过滤注释和空行，提取有效内容
                valid_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        valid_lines.append(line)

                # 每段需要至少两行：原始文本和修正文本
                if len(valid_lines) >= 2:
                    wrong = valid_lines[0]
                    right = valid_lines[1]

                    if wrong and right:
                        # 提取差异片段
                        fragments = extract_diff_fragments(wrong, right)
                        if not fragments:
                            # 如果提取不到差异（可能整句都不同），用整个错句
                            fragments = [wrong]

                        record = RectifyRecord(wrong, right, fragments)
                        new_records.append(record)
                        logger.debug(f"加载纠错: '{wrong}' => '{right}', 检索词: {fragments}")

            with self._lock:
                self.records = new_records

            count = len(new_records)
            if count > 0:
                total_fragments = sum(len(r.fragments) for r in new_records)
                logger.debug(f"已加载 {count} 条纠错历史，{total_fragments} 个检索片段，耗时 {time.time() - start_time:.3f}s")
                logger.info(f"已载入 {count} 条 LLM 纠错历史")
                
        except Exception as e:
            logger.error(f"加载纠错历史失败: {e}")

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """
        检索相关的纠错历史
        
        Args:
            text: 输入文本（语音识别结果）
            top_k: 最大结果数（可在角色配置中设置）
            
        Returns:
            [(wrong, right, score), ...] 按分数降序
        """
        if not text or not self.records:
            return []
            
        input_phonemes = get_phoneme_seq(text)
        if not input_phonemes:
            return []
        
        logger.debug(f"纠错检索: 输入='{text}', 音素数={len(input_phonemes)}")
            
        # 每条记录的最高匹配分数
        record_scores: Dict[int, float] = {}
        
        with self._lock:
            records = self.records[:]
        
        for idx, record in enumerate(records):
            best_score = 0.0
            
            # 用每个检索片段与输入匹配，取最高分
            for fragment, frag_phonemes in record.fragment_phonemes.items():
                if not frag_phonemes:
                    continue
                    
                # 在输入中查找片段
                min_dist = fuzzy_substring_distance(input_phonemes, frag_phonemes)
                denom = len(frag_phonemes) if len(frag_phonemes) > 0 else 1
                score = 1.0 - (min_dist / denom)
                
                if score > best_score:
                    best_score = score
            
            if best_score >= self.threshold:
                record_scores[idx] = best_score
                
        # 按分数排序
        sorted_indices = sorted(record_scores.keys(), key=lambda i: record_scores[i], reverse=True)
        
        results = []
        for idx in sorted_indices[:top_k]:
            record = records[idx]
            score = record_scores[idx]
            results.append((record.wrong, record.right, round(score, 3)))
            
        if results:
            logger.debug(f"纠错匹配结果: {results}")
        else:
            logger.debug(f"未匹配到纠错历史（阈值={self.threshold}）")
            
        return results

    def format_prompt(self, text: str, top_k: int = 5) -> str:
        """
        生成提示词

        Args:
            text: 输入文本
            top_k: 最大结果数

        Returns:
            包含纠错历史的提示词段落，无匹配则返回空字符串
        """
        logger.debug(f"纠错 RAG format_prompt 调用: text='{text}', top_k={top_k}, 已加载记录数={len(self.records) if self.records else 0}")

        if not self.records:
            logger.debug(f"纠错 RAG: 没有已加载的纠错记录")
            return ""

        results = self.search(text, top_k=top_k)
        if not results:
            logger.debug(f"纠错 RAG: 未检索到相关纠错历史")
            return ""

        lines = ["参考以下历史纠错："]
        for wrong, right, score in results:
            lines.append(f"- {wrong} => {right}")

        result = "\n".join(lines)
        logger.debug(f"纠错 RAG: 生成提示词:\n{result}")
        return result


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n--- 扩展逻辑测试 ---")
    
    # 测试 extract_diff_fragments 的扩展逻辑
    test_cases_expand = [
        ("原锯子", "原句子"),      # 单字差异，应扩展
        ("天器好", "天气好"),      # 单字差异，应扩展
        ("今天不做", "今天不错"),  # 够长，不需扩展
        ("caps riter", "CapsWriter"),
        ("helo world", "hello world"),  # 单个字母差异
    ]
    
    print("\n差异片段提取（带扩展）：")
    for wrong, right in test_cases_expand:
        fragments = extract_diff_fragments(wrong, right)
        print(f"  '{wrong}' => '{right}'")
        print(f"    检索词: {fragments}")
    
    print("\n--- RectificationRAG 完整测试 ---")
    
    # 创建临时文件
    test_file = Path("test_rectify.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""# 中文纠错（含单字修改）
原锯子 => 原句子
天器好 => 天气好
康灰主持 => 康辉主持
东方菜富 => 东方财富

# 英文纠错
caps riter => CapsWriter
helo world => hello world
micro soft => Microsoft
pythn => Python
""")
        
    try:
        rag = RectificationRAG(str(test_file), threshold=0.5)
        
        print("\n=== 单字修改测试（验证扩展） ===")
        
        print("\n搜索 '天器很好啊':")
        res = rag.search("天器很好啊")
        print(f"  结果: {res}")
        
        print("\n搜索 '这个原锯子不对':")
        res = rag.search("这个原锯子不对")
        print(f"  结果: {res}")
        
        print("\n=== 中英混合测试 ===")
        
        print("\n搜索 '康灰用caps riter写代码':")
        res = rag.search("康灰用caps riter写代码")
        print(f"  结果: {res}")
        
        print("\n搜索 'helo world program':")
        res = rag.search("helo world program")
        print(f"  结果: {res}")
        
        print("\n=== Prompt 生成 ===")
        print(rag.format_prompt("康灰在东方菜富用caps riter"))

    finally:
        if test_file.exists():
            test_file.unlink()
