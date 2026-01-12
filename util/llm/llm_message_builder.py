
# coding: utf-8
"""
LLM 消息构建模块

负责组装 LLM 请求的完整上下文，包括：
1. System Prompt（系统提示词）
2. 对话历史
3. 热词列表（RAG 检索）
4. 纠错历史（RAG 检索）
5. 用户输入
6. 图片数据（可选）
"""

from __future__ import annotations

import json
from typing import List, Dict, Optional, Tuple, Any

from util.llm.llm_role_config import RoleConfig
from util.llm.llm_constants import estimate_tokens
from util.logger import get_logger

logger = get_logger('client')


class MessageBuilder:
    """LLM 消息构建器"""

    def __init__(self):
        """
        初始化消息构建器
        """
        # 延迟导入避免循环依赖
        pass

    def _get_rectify_rag(self):
        """从 HotwordManager 获取 RectificationRAG"""
        from util.hotword import get_hotword_manager
        manager = get_hotword_manager()
        return manager.get_rectify_rag()

    def build_messages(
        self,
        role_config: RoleConfig,
        user_content: str,
        context_manager: Any = None,
        image_data: Optional[str] = None,
        hotwords: Optional[List[Tuple[str, float]]] = None,
        selection_text: str = ""
    ) -> List[Dict]:
        """
        构建 LLM 请求消息

        Args:
            role_config: 角色配置
            user_content: 用户输入内容
            context_manager: 上下文管理器（历史记录）
            image_data: 图片数据（base64 编码）
            hotwords: 匹配的热词列表 [(热词, 分数), ...]
            selection_text: 用户选中的文字

        Returns:
            完整的消息列表
        """
        messages = []

        # 1. System Prompt
        if role_config.system_prompt:
            messages.append({
                "role": "system",
                "content": role_config.system_prompt
            })

        # 2. 对话历史
        if context_manager:
            if hasattr(context_manager, 'history') and isinstance(context_manager.history, list):
                messages.extend(context_manager.history)
            elif isinstance(context_manager, list):
                messages.extend(context_manager)

        # 3. 用户内容构建
        user_content_parts = []

        # 缓存角色配置属性（避免重复 getattr）
        enable_hotwords = getattr(role_config, 'enable_hotwords', False)
        enable_rectify = getattr(role_config, 'enable_rectify', False)

        logger.debug(f"[消息构建] enable_hotwords={enable_hotwords}, hotwords数量={len(hotwords) if hotwords else 0}")
        logger.debug(f"[消息构建] enable_rectify={enable_rectify}")

        # 添加 RAG 热词列表（根据角色配置）
        if enable_hotwords and hotwords:
            hotwords_prompt = self._format_hotwords_prompt(hotwords)
            if hotwords_prompt:
                user_content_parts.append(hotwords_prompt)
                logger.debug(f"[消息构建] 已添加热词列表")

        # 添加纠错历史（根据角色配置）
        if enable_rectify:
            logger.debug(f"[消息构建] 开始调用 rectify_rag.format_prompt")
            rectify_rag = self._get_rectify_rag()
            if rectify_rag:
                rectify_prompt = rectify_rag.format_prompt(user_content)  
                if rectify_prompt:
                    user_content_parts.append(rectify_prompt)
                    logger.debug(f"[消息构建] 已添加纠错历史")
                else:
                    logger.debug(f"[消息构建] rectify_prompt 为空")
            else:
                logger.debug(f"[消息构建] rectify_rag 为 None")
        else:
            logger.debug(f"[消息构建] 跳过纠错历史: enable_rectify={enable_rectify}")

        # 添加选中文字（根据角色配置）
        if selection_text:
            selection_prompt = self._format_selection_prompt(selection_text)
            if selection_prompt:
                user_content_parts.append(selection_prompt)

        real_user_content = user_content

        # if user_content_parts:
        if True:
            # 在开头添加上下文
            context_str = "\n\n".join(user_content_parts)
            real_user_content = f"{context_str}\n\n用户输入：\n{user_content}"

        # 构建最终用户消息
        final_user_msg = {"role": "user", "content": real_user_content}

        # 处理图片数据（注意：有图片时会将 content 改为列表格式）
        if image_data:
             final_user_msg["content"] = [
                 {"type": "text", "text": real_user_content},
                 {"type": "image_url", "image_url": {"url": image_data}}
             ]

        messages.append(final_user_msg)

        # 打印完整的上下文 JSON
        self._debug_print_messages(role_config.name, role_config, messages)

        return messages

    def _format_hotwords_prompt(self, hotwords: List[Tuple[str, float]]) -> str:
        """
        将检索结果格式化为提示词

        Args:
            hotwords: [(热词, 分数), ...]

        Returns:
            格式化的提示字符串
        """
        if not hotwords:
            return ""

        # 提取热词（只保留词，不保留分数）
        hotword_list = [hw for hw, _ in hotwords]
        return f"热词列表：[{', '.join(hotword_list)}]"

    def _format_selection_prompt(self, selection_text: str) -> str:
        """
        将选中文字格式化为提示词

        Args:
            selection_text: 选中的文字

        Returns:
            格式化的提示字符串
        """
        if not selection_text or not selection_text.strip():
            return ""

        return f"选中文字：\n{selection_text}"

    def _debug_print_messages(
        self,
        role_name: str,
        role_config: RoleConfig,
        messages: List[Dict]
    ):
        """打印调试信息（上下文统计和完整消息）"""
        try:
            # 计算上下文统计信息
            total_tokens = sum(
                estimate_tokens(msg['content'])
                for msg in messages
            )
            history_count = len([m for m in messages if m['role'] in ['user', 'assistant']])
            max_context = role_config.max_context_length
            usage_percent = (total_tokens / max_context * 100) if max_context > 0 else 0

            debug_msg = [
                f"\n{'='*70}",
                f"[LLM 请求] 角色: {role_name}",
                f"  上下文统计:",
                f"    历史消息数: {history_count} 条",
                f"    总 Token 数: {total_tokens} / {max_context} ({usage_percent:.1f}%)",
                f"    剩余空间: {max_context - total_tokens} tokens",
                f"    清理阈值: 80% (约 {int(max_context * 0.8)} tokens)"
            ]

            if usage_percent > 80:
                debug_msg.append(f"    ⚠️  警告: 上下文超过 80%，已触发自动清理")
            elif usage_percent > 60:
                debug_msg.append(f"    ⚡ 提示: 上下文使用超过 60%")

            debug_msg.append(f"{'='*70}")
            debug_msg.append(json.dumps(messages, ensure_ascii=False, indent=2))
            debug_msg.append(f"{'='*70}\n")

            logger.debug("\n".join(debug_msg))
        except Exception as e:
            logger.error(f"调试输出失败: {e}")
