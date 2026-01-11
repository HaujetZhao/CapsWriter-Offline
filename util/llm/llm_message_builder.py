
import json
import logging
from typing import List, Dict, Optional, Any

from util.llm.llm_role_config import RoleConfig
from util.llm.llm_constants import estimate_tokens
from util.logger import get_logger

# Type hinting only
try:
    from util.llm.llm_rag_adapter import HotwordsRAG
except ImportError:
    HotwordsRAG = Any

try:
    from util.hotword.rag_llm_rectify import LLMRectifyRAG
except ImportError:
    LLMRectifyRAG = Any

logger = get_logger('client')

class MessageBuilder:
    def __init__(
        self, 
        rag: Optional[HotwordsRAG] = None, 
        rectify_rag: Optional[LLMRectifyRAG] = None
    ):
        self.rag = rag
        self.rectify_rag = rectify_rag

    def build_messages(
        self, 
        role_config: RoleConfig,
        user_content: str, 
        context_manager=None,
        image_data: str = None
    ) -> List[Dict]:
        
        messages = []
        
        # 1. System Prompt
        if role_config.system_prompt:
            messages.append({
                "role": "system",
                "content": role_config.system_prompt
            })
            
        # 2. History
        if context_manager:
            if hasattr(context_manager, 'history') and isinstance(context_manager.history, list):
                messages.extend(context_manager.history)
            elif isinstance(context_manager, list):
                messages.extend(context_manager)

        # 3. User Content Construction
        user_content_parts = []
        
        # Add RAG Hotwords (根据角色配置)
        if self.rag and getattr(role_config, 'enable_hotwords', False):
            hotwords_prompt = self.rag.format_prompt(user_content)
            if hotwords_prompt:
                 user_content_parts.append(hotwords_prompt)
                 
        # Add Rectify History (根据角色配置)
        if self.rectify_rag and getattr(role_config, 'enable_rectify_history', False):
            rectify_prompt = self.rectify_rag.format_prompt(user_content)
            if rectify_prompt:
                user_content_parts.append(rectify_prompt)

        real_user_content = user_content
        
        if user_content_parts:
            # Add context at the beginning
            context_str = "\n\n".join(user_content_parts)
            real_user_content = f"{context_str}\n\n我的输入：\n{user_content}"
            
        # Construct Final User Message
        final_user_msg = {"role": "user", "content": real_user_content}
        
        # Handle Image
        if image_data:
             final_user_msg["content"] = [
                 {"type": "text", "text": real_user_content},
                 {"type": "image_url", "image_url": {"url": image_data}}
             ]

        messages.append(final_user_msg)
        
        # Debug Print - 打印完整的 context JSON
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
            logger.error(f"Debug print failed: {e}")
