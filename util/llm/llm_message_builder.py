
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
from . import logger


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
            if hasattr(context_manager, 'get_history') and callable(context_manager.get_history):
                messages.extend(context_manager.get_history())
            elif hasattr(context_manager, 'history') and isinstance(context_manager.history, list):
                messages.extend(context_manager.history)
            elif isinstance(context_manager, list):
                messages.extend(context_manager)

        # 3. 用户内容构建 (集中式构建，方便管理格式)
        context_parts = []

        # 3.1 热词列表
        if role_config.enable_hotwords and hotwords:
            logger.debug(f"[DEBUG] hotwords type={type(hotwords)}, len={len(hotwords)}")
            if hotwords:
                logger.debug(f"[DEBUG] hotwords[0] type={type(hotwords[0])}, value={hotwords[0]}")
            try:
                # hotwords 结构为 [(source, match, score), ...]
                words = [item[1] for item in hotwords]
                        
                if words:
                    context_parts.append(f"{role_config.prompt_prefix_hotwords}[{', '.join(words)}]")
                    logger.debug(f"[消息构建] 已添加热词列表")
            except Exception as e:
                logger.error(f"[ERROR] Failed to process hotwords: {e}")
                logger.error(f"[ERROR] hotwords details: {[(type(hw), hw) for hw in hotwords[:5]]}")
                raise

        # 3.2 纠错历史 (从 RAG 获取原始数据并在本地格式化)
        if role_config.enable_rectify:
            rectify_rag = self._get_rectify_rag()
            if rectify_rag:
                matches = rectify_rag.search(user_content)
                if matches:
                    lines = [role_config.prompt_prefix_rectify]
                    for wrong, right, _ in matches:
                        lines.append(f"- {wrong} => {right}")
                    context_parts.append("\n".join(lines))
                    logger.debug(f"[消息构建] 已从 RAG 获取并添加 {len(matches)} 条纠错历史记录")

        # 3.3 选中文字
        if selection_text:
             context_parts.append(f"{role_config.prompt_prefix_selection}{selection_text}")
             logger.debug(f"[消息构建] 已添加选中文字")

        # 3.4 最终组装
        context_str = "\n\n".join(context_parts)
        context_str = context_str + "\n\n" if context_str else ""

        user_content = f"{context_str}{role_config.prompt_prefix_input}{user_content}"

        # 构建最终用户消息
        final_user_msg = {"role": "user", "content": user_content}

        # 处理图片数据（注意：有图片时会将 content 改为列表格式）
        if image_data:
             final_user_msg["content"] = [
                 {"type": "text", "text": user_content},
                 {"type": "image_url", "image_url": {"url": image_data}}
             ]

        messages.append(final_user_msg)

        # 打印完整的上下文 JSON
        self._debug_print_messages(role_config.name, role_config, messages)

        return messages

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
                f"[LLM 请求] 角色: {role_name if role_name else '默认'}",
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
            
            # 1. 首先用 DEBUG 级别打印详细统计信息
            logger.debug("\n".join(debug_msg))

            # 2. 只有最新的一条用户消息用 INFO 打印
            last_msg = messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, list):
                # 处理多模态格式，提取文本
                content = "\n".join([item.get('text', '') for item in content if item.get('type') == 'text'])

            info_msg = [
                f"\n{'='*70}",
                f"[LLM 请求] 角色: {role_name if role_name else '默认'}",
                f"{content}",
                f"{'='*70}\n"
            ]
            logger.info("\n".join(info_msg))

        except Exception as e:
            logger.error(f"消息日志输出失败: {e}")
