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
        """检查历史是否过期"""
        if not self.last_interaction:
            return False

        elapsed = time.time() - self.last_interaction
        return elapsed > self.forget_duration

    def _trim_history(self):
        """修剪历史"""
        max_messages = self.max_length // 100

        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
