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
from typing import List, Tuple, Dict, Set, Optional
from difflib import SequenceMatcher
from dataclasses import dataclass

from .algo_phoneme import get_phoneme_seq, normalize_text, Phoneme
from .algo_calc import fuzzy_substring_distance
try:
    from util.logger import get_logger
    logger = get_logger('client')
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class Fragment:
    """
    纠错片段

    Attributes:
        text: 片段文本
        source_text: 来源文本（错句或正句的完整文本）
        start: 片段在 source_text 中的起始位置
        end: 片段在 source_text 中的结束位置
    """
    text: str
    source_text: str
    start: int
    end: int

    def __repr__(self):
        return f"Fragment('{self.text}', pos={self.start}:{self.end})"

def _get_word_boundaries(text: str) -> List[Tuple[int, int, str]]:
    """
    获取文本中所有单词的边界
    返回: [(start, end, word), ...] 每个单词的起止位置和内容
    """
    boundaries = []
    i, n = 0, len(text)
    while i < n:
        if not (text[i].isalnum() or '\u4e00' <= text[i] <= '\u9fff'):
            i += 1
            continue
        start = i
        if '\u4e00' <= text[i] <= '\u9fff':
            i += 1
        elif text[i].isalnum():
            last_was_lower = text[i].islower()
            while i < n and text[i].isalnum():
                if text[i].isupper() and last_was_lower and i > start:
                    break
                last_was_lower = text[i].islower()
                i += 1
        boundaries.append((start, i, text[start:i]))
    return boundaries


def _expand_by_words(text: str, start: int, end: int, expand_count: int = 1) -> Tuple[int, int]:
    """按单词数量向左右扩展片段"""
    bounds = _get_word_boundaries(text)
    start_idx = next((i for i, b in enumerate(bounds) if b[0] == start), None)
    end_idx = next((i + 1 for i, b in enumerate(bounds) if b[1] == end), None)

    if start_idx is None or end_idx is None:
        return start, end

    new_start = bounds[max(0, start_idx - expand_count)][0]
    new_end = bounds[min(len(bounds), end_idx + expand_count) - 1][1]
    return new_start, new_end


def _extract_continuous_fragment(bounds: List[Tuple[int, int, str]], start_idx: int, end_idx: int, original_text: str) -> str:
    """从边界列表中提取连续的片段（保留原始文本中的分隔符）"""
    if start_idx >= end_idx or start_idx >= len(bounds):
        return ""
    return original_text[bounds[start_idx][0] : bounds[end_idx - 1][1]]


def extract_diff_fragments(wrong: str, right: str, zh_min_phonemes: int = 4, expand_words: int = 1) -> List[str]:
    """
    提取两个句子之间的差异片段（包括错误版本和正确版本）
    基于单词序列进行精准提取
    """
    # 获取两个文本的单词边界
    wrong_bounds = _get_word_boundaries(wrong)
    right_bounds = _get_word_boundaries(right)

    # 提取差异块
    matcher = SequenceMatcher(None, [b[2] for b in wrong_bounds], [b[2] for b in right_bounds])
    fragments: List[Fragment] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ('replace', 'delete') and i2 > i1:
            frag_text = _extract_continuous_fragment(wrong_bounds, i1, i2, wrong)
            if frag_text:
                fragments.append(Fragment(frag_text, wrong, wrong_bounds[i1][0], wrong_bounds[i2-1][1]))
        if tag in ('replace', 'insert') and j2 > j1:
            frag_text = _extract_continuous_fragment(right_bounds, j1, j2, right)
            if frag_text:
                fragments.append(Fragment(frag_text, right, right_bounds[j1][0], right_bounds[j2-1][1]))

    # 智能过滤和扩展
    result = []
    for frag in fragments:
        phonemes = get_phoneme_seq(frag.text)
        if not phonemes: continue

        # 语言判定与扩展策略
        if any(p.lang != 'zh' for p in phonemes) or len(phonemes) >= zh_min_phonemes:
            result.append(frag.text)
        else:
            # 中文片段太短，扩展单词
            exp_start, exp_end = _expand_by_words(frag.source_text, frag.start, frag.end, expand_words)
            expanded_frag = frag.source_text[exp_start:exp_end]
            result.append(expanded_frag if expanded_frag else frag.text)

    return list(dict.fromkeys(result))  # 去重并保持顺序


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

    def __init__(self, rectify_file: str = 'hot-rectify.txt', threshold: float = 0.5):
        """
        初始化

        Args:
            rectify_file: 纠错历史文件路径
            threshold: 相似度阈值（默认0.5）
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

    def _score_record(self, input_phonemes: List[Phoneme], record: RectifyRecord) -> Tuple[float, List[dict]]:
        """计算单条记录与输入音素序列的匹配得分及片段详情"""
        fragment_details = []
        for fragment, frag_phonemes in record.fragment_phonemes.items():
            if not frag_phonemes: continue
            
            # 计算相似度 (1 - 归一化编辑距离)
            min_dist = fuzzy_substring_distance(input_phonemes, frag_phonemes)
            score = 1.0 - (min_dist / len(frag_phonemes))
            
            fragment_details.append({
                'fragment': fragment,
                'score': round(score, 3),
                'phonemes': len(frag_phonemes)
            })
            
        if not fragment_details:
            return 0.0, []
            
        # 按得分排序，记录得分为最高片段分
        fragment_details.sort(key=lambda x: x['score'], reverse=True)
        return fragment_details[0]['score'], fragment_details

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """检索相关的纠错历史"""
        if not text or not self.records: return []
            
        input_phonemes = get_phoneme_seq(text)
        if not input_phonemes: return []
        
        logger.debug(f"纠错检索: 输入='{text}', 音素数={len(input_phonemes)}")
        
        with self._lock:
            records = self.records[:]
        
        matches = []
        for record in records:
            best_score, _ = self._score_record(input_phonemes, record)
            if best_score >= self.threshold:
                matches.append((record.wrong, record.right, round(best_score, 3)))
                
        # 按分数排序并截断
        matches.sort(key=lambda x: x[2], reverse=True)
        results = matches[:top_k]
            
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

        lines = ["纠错历史："]
        for wrong, right, score in results:
            lines.append(f"- {wrong} => {right}")

        result = "\n".join(lines)
        logger.debug(f"纠错 RAG: 生成提示词:\n{result}")
        return result

    def search_detailed(self, text: str, top_k: int = 5) -> List[dict]:
        """检索相关的纠错历史（详细版）"""
        if not text or not self.records: return []

        input_phonemes = get_phoneme_seq(text)
        if not input_phonemes: return []

        with self._lock:
            records = self.records[:]

        results = []
        for record in records:
            best_score, fragment_details = self._score_record(input_phonemes, record)
            if best_score >= self.threshold:
                results.append({
                    'wrong': record.wrong,
                    'right': record.right,
                    'score': best_score,
                    'fragments': fragment_details
                })

        # 按最高得分排序并截断
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]


if __name__ == "__main__":
    import sys
    import io
    # 设置 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import logging
    logging.basicConfig(level=logging.INFO)

    print("\n=== 纠错检索详细测试 ===\n")

    # 使用实际的 hot-rectify.txt 文件
    rectify_file = Path("hot-rectify.txt")
    if not rectify_file.exists():
        print(f"文件不存在: {rectify_file}")
        sys.exit(1)

    # 加载纠错历史（使用默认阈值 0.5）
    rag = RectificationRAG(str(rectify_file))

    print(f"已加载 {len(rag.records)} 条纠错记录\n")

    # 显示每条记录的检索词
    print("=" * 80)
    print("纠错记录及其检索词：")
    print("=" * 80)
    for i, record in enumerate(rag.records, 1):
        print(f"\n{i}. {record.wrong} => {record.right}")
        print(f"   检索词 ({len(record.fragments)} 个):")
        for frag in record.fragments:
            phonemes = get_phoneme_seq(frag)
            print(f"     - '{frag}' (音素数: {len(phonemes)})")

    # 测试检索
    print("\n" + "=" * 80)
    print("检索测试：")
    print("=" * 80)

    test_queries = [
        "cloud 这个软件是非常好的",
        "我最近正在使用 Cloud Code",
        "你能看到关于 Cloud Code 的纠错信息吗",
        "Cloud这个软件很好用",
        "这样不就可以了",  # 修改：包含 "不" 字的查询
    ]

    for query in test_queries:
        print(f"\n搜索: '{query}'")
        print("-" * 60)

        # 使用详细检索
        results = rag.search_detailed(query)

        if results:
            for r in results:
                print(f"  错误: {r['wrong']}")
                print(f"  正确: {r['right']}")
                print(f"  最高得分: {r['score']}")
                print(f"  检索片段详情:")
                for frag in r['fragments']:
                    print(f"    - '{frag['fragment']}' 得分={frag['score']} 音素数={frag['phonemes']}")
        else:
            # 即使没有匹配，也显示所有记录的得分
            print(f"  未匹配到纠错历史（所有记录得分均低于阈值 {rag.threshold}）")
            print(f"  详细得分:")
            for record in rag.records:
                # 计算该记录的最高得分
                input_phonemes = get_phoneme_seq(query)
                best_score = 0.0
                best_fragment = ""
                for fragment, frag_phonemes in record.fragment_phonemes.items():
                    if not frag_phonemes:
                        continue
                    min_dist = fuzzy_substring_distance(input_phonemes, frag_phonemes)
                    denom = len(frag_phonemes) if len(frag_phonemes) > 0 else 1
                    score = 1.0 - (min_dist / denom)
                    if score > best_score:
                        best_score = score
                        best_fragment = fragment
                print(f"    - {record.wrong} => {record.right}")
                print(f"      最高得分: {best_score:.3f} (片段: '{best_fragment}')")

    print("\n" + "=" * 80)
