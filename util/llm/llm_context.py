"""
LLM 上下文管理器

功能：
1. 管理对话历史
2. 自动清理过期对话
3. 修剪历史长度
"""

import time
from typing import Dict, List
from threading import Lock


class ContextManager:
    """对话上下文管理器"""

    def __init__(self, max_length: int = 2000, forget_duration: int = 300):
        self.max_length = max_length
        self.forget_duration = forget_duration
        self.history = []
        self.last_interaction = None
        self._lock = Lock()

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        with self._lock:
            timestamp = time.time()
            self.history.append({
                'timestamp': timestamp,
                'role': role,
                'content': content,
            })
            self.last_interaction = timestamp
            self._trim_history()

    def get_history(self) -> List[Dict]:
        """获取对话历史"""
        with self._lock:
            if self._is_expired():
                self.history = []
                return []

            return [
                {'role': msg['role'], 'content': msg['content']}
                for msg in self.history
            ]

    def _is_expired(self) -> bool:
        """检查历史是否过期

        forget_duration=0 表示永不遗忘
        """
        # forget_duration 为 0 表示永不遗忘
        if self.forget_duration == 0:
            return False

        if not self.last_interaction:
            return False

        elapsed = time.time() - self.last_interaction
        return elapsed > self.forget_duration

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量

        使用简单的启发式方法：
        - 英文：约 4 字符 = 1 token
        - 中文：约 1.5 字符 = 1 token
        - 混合文本按比例计算
        """
        if not text:
            return 0

        # 统计中文字符数量
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 统计非中文字符数量
        other_chars = len(text) - chinese_chars

        # 中文字符：约 1.5 字符 = 1 token
        # 英文和其他字符：约 4 字符 = 1 token
        tokens = int(chinese_chars / 1.5 + other_chars / 4)

        return max(tokens, 1)  # 至少 1 个 token

    def _trim_history(self):
        """基于 token 数量智能修剪历史

        策略：
        1. 如果超过限制的 80%，立即清理
        2. 保留 20% 空间给模型思考输出
        3. 从最早的消息开始删除，优先保留最近的对话
        """
        if not self.history:
            return

        # 计算当前历史的总 token 数
        total_tokens = sum(
            self._estimate_tokens(msg['content'])
            for msg in self.history
        )

        # 使用 80% 阈值，保留 20% 给模型输出
        target_tokens = int(self.max_length * 0.8)

        # 如果总 token 数在 80% 范围内，不需要修剪
        if total_tokens <= target_tokens:
            return

        print(f"[上下文裁剪] 当前 {total_tokens} tokens ({total_tokens/self.max_length*100:.1f}%)，触发清理（阈值：{target_tokens} tokens, 80%）")

        # 从头部（最旧的消息）开始删除，直到满足 80% 限制
        removed_count = 0
        while self.history and total_tokens > target_tokens:
            # 删除最旧的消息
            removed_msg = self.history.pop(0)
            removed_tokens = self._estimate_tokens(removed_msg['content'])
            total_tokens -= removed_tokens
            removed_count += 1

        # 调试信息：打印裁剪结果
        if len(self.history) > 0:
            final_tokens = sum(self._estimate_tokens(msg['content']) for msg in self.history)
            print(f"[上下文裁剪] 已删除 {removed_count} 条旧消息，保留 {len(self.history)} 条消息")
            print(f"[上下文裁剪] 当前约 {final_tokens} tokens ({final_tokens/self.max_length*100:.1f}%)，剩余空间 {self.max_length - final_tokens} tokens")
