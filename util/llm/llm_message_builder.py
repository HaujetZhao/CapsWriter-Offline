"""
LLM 消息构建器

功能：
1. 构建发送给 LLM 的 messages 列表
2. 整合 system prompt, history, hotwords, clipboard, user input
3. 提供 debug 输出
"""
import json
from typing import Dict, List
from util.llm.llm_role_config import RoleConfig
from util.llm.llm_context import ContextManager


class MessageBuilder:
    """LLM 消息构建器"""

    def __init__(self, rag=None):
        """
        Args:
            rag: 热词 RAG 实例（可选）
        """
        self.rag = rag

    def build_messages(
        self,
        role_config: RoleConfig,
        text: str,
        context_manager: ContextManager = None
    ) -> List[Dict]:
        """构建消息列表

        Args:
            role_config: 角色配置（RoleConfig 对象）
            text: 输入文本（已去除角色前缀）
            context_manager: 上下文管理器（可选）

        Returns:
            消息列表（messages[-1]['content'] 是完整的用户提示词）
        """
        role_name = role_config.name

        messages = [
            {'role': 'system', 'content': role_config.system_prompt.strip()}
        ]

        # 添加历史
        if role_config.enable_history and context_manager:
            history = context_manager.get_history()
            messages.extend(history)

        # 热词 RAG - 生成提示并添加到用户消息
        user_content_parts = []

        if role_config.enable_hotwords and self.rag:
            hotword_prompt = self.rag.format_prompt(text)
            if hotword_prompt:
                user_content_parts.append(hotword_prompt)

        # 获取选中的文字（模拟 Ctrl+C）
        if role_config.enable_read_selection:
            from util.llm.llm_get_selection import get_selected_text, record_selection_usage
            selected_text = get_selected_text(role_config)
            if selected_text:
                user_content_parts.append(f"选中的文字：{selected_text}")
                # 记录使用的选中文字，避免下一轮重复加入
                record_selection_usage(role_config, selected_text)

        # 用户输入
        if user_content_parts:
            user_content = "\n\n".join(user_content_parts) + "\n\n用户输入：" + text
        else:
            user_content = text

        messages.append({'role': 'user', 'content': user_content})

        # DEBUG: 打印投喂给模型的完整内容（原始JSON格式）
        self._debug_print_messages(role_name, role_config, messages)

        return messages

    def _debug_print_messages(
        self,
        role_name: str,
        role_config: RoleConfig,
        messages: List[Dict]
    ):
        """打印调试信息（上下文统计和完整消息）"""
        # 计算上下文统计信息
        total_tokens = sum(
            ContextManager._estimate_tokens(None, msg['content'])
            for msg in messages
        )
        history_count = len([m for m in messages if m['role'] in ['user', 'assistant']])
        max_context = role_config.max_context_length
        usage_percent = (total_tokens / max_context * 100) if max_context > 0 else 0

        print(f"\n{'='*70}")
        print(f"[LLM 请求] 角色: {role_name}")
        print(f"  上下文统计:")
        print(f"    历史消息数: {history_count} 条")
        print(f"    总 Token 数: {total_tokens} / {max_context} ({usage_percent:.1f}%)")
        print(f"    剩余空间: {max_context - total_tokens} tokens")
        print(f"    清理阈值: 80% (约 {int(max_context * 0.8)} tokens)")

        if usage_percent > 80:
            print(f"    ⚠️  警告: 上下文超过 80%，已触发自动清理")
        elif usage_percent > 60:
            print(f"    ⚡ 提示: 上下文使用超过 60%")

        print(f"{'='*70}")
        print(json.dumps(messages, ensure_ascii=False, indent=2))
        print(f"{'='*70}\n")
