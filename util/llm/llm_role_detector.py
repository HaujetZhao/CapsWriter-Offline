"""
LLM 角色检测器

功能：
1. 检测文本是否匹配某个角色前缀
2. 返回对应的角色配置和去除前缀后的文本
3. 检测指令关键词（清除历史、撤回上一轮、显示上一轮、复制结果、复制全部上下文、复制当前角色上下文）
"""
from typing import Tuple, Optional
from util.llm.llm_role_config import RoleConfig
from util.llm.llm_interfaces import IRoleLoader
from . import logger
from config import ClientConfig

# 指令标记常量
COMMAND_TOKEN = "__COMMAND__"

# 常量定义
PREFIX_STRIP_PUNCTUATION = '：，。？！,.?! '
ROLE_SORT_KEY = lambda item: len(item[1].name)


class RoleDetector:
    """角色检测器 - 负责从输入文本中检测角色"""

    def __init__(self, role_loader: IRoleLoader):
        """
        Args:
            role_loader: 角色加载器实例
        """
        self.role_loader = role_loader
        # 缓存角色列表和排序结果
        self._cached_roles = None
        self._cached_roles_sorted = None
        self._roles_hash = None

    def _get_sorted_roles(self):
        """获取排序后的角色列表（带缓存和变化检测）"""
        current_roles = self.role_loader.get_roles()
        # 使用角色名称列表的排序字符串作为哈希值（检测角色名称和配置变化）
        current_hash = hash(','.join(sorted(current_roles.keys())))
        
        # 如果角色列表发生变化，清除缓存
        if self._roles_hash != current_hash:
            self._cached_roles = current_roles
            self._cached_roles_sorted = sorted(
                current_roles.items(),
                key=ROLE_SORT_KEY,
                reverse=True
            )
            self._roles_hash = current_hash
            logger.debug("角色列表已更新，已刷新检测缓存")
        
        return self._cached_roles_sorted

    def detect(self, text: str) -> Tuple[Optional[RoleConfig], str]:
        """
        检测文本是否匹配某个角色前缀或指令关键词

        Args:
            text: 输入文本

        Returns:
            (role_config, content) - role_config 是 RoleConfig 对象，
            content 是去除前缀后的文本
        """
        # ======================================================================
        # --- 指令处理函数（提前定义，避免重复导入）---
        # ======================================================================
        
        # 清除历史指令
        def _execute_clear_history():
            from util.llm.llm_handler import clear_llm_history
            clear_llm_history()
            logger.info(f"检测到清除指令 '{text}'，已清除所有角色的对话历史记录")
            toast("清除成功：已清除所有角色的对话历史记录", duration=3000, bg="#075077")

        # 撤回上一轮对话指令
        def _execute_revoke_last_turn():
            from util.llm.llm_handler import revoke_last_turn
            success, message = revoke_last_turn()
            if success:
                logger.info(f"检测到撤回指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#075077")
            else:
                logger.warning(f"检测到撤回指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#d9534f")

        # 显示最近对话指令
        def _execute_show_last_turn():
            from util.llm.llm_handler import show_last_turn
            success, message = show_last_turn()
            if success:
                logger.info(f"检测到显示指令 '{text}'，{message}")
                toast(message, duration=5000, bg="#075077")
            else:
                logger.warning(f"检测到显示指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#d9534f")

        # 复制结果指令
        def _execute_copy_result():
            from util.client.state import get_state
            from util.llm.llm_clipboard import copy_to_clipboard
            state = get_state()
            copy_text = state.last_output_text  # 使用新变量名，避免覆盖外层 text
            if copy_text:
                copy_to_clipboard(copy_text)
                logger.info(f"检测到复制结果指令 '{text}'，已复制到剪贴板")
                toast("复制成功：已复制结果到剪贴板", duration=3000, bg="#075077")
            else:
                logger.warning(f"检测到复制结果指令 '{text}'，但没有可复制的内容")
                toast("复制失败：没有可复制的内容", duration=3000, bg="#d9534f")

        # 复制全部上下文指令
        def _execute_copy_all_context():
            from util.llm.llm_handler import copy_all_context
            success, message = copy_all_context()
            if success:
                logger.info(f"检测到复制全部上下文指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#075077")
            else:
                logger.warning(f"检测到复制全部上下文指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#d9534f")

        # 复制当前角色上下文指令
        def _execute_copy_current_role_context():
            from util.llm.llm_handler import copy_current_role_context
            success, message = copy_current_role_context()
            if success:
                logger.info(f"检测到复制当前角色上下文指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#075077")
            else:
                logger.warning(f"检测到复制当前角色上下文指令 '{text}'，{message}")
                toast(message, duration=3000, bg="#d9534f")

        # ======================================================================
        # --- 指令定义（统一管理）---
        # ======================================================================
        
        # 将关键词列表转换为集合（只需转换一次）
        keyword_sets = {
            'clear_history': set(ClientConfig.clear_history_keywords) if ClientConfig.clear_history_keywords else set(),
            'revoke_last_turn': set(ClientConfig.revoke_last_turn_keywords) if ClientConfig.revoke_last_turn_keywords else set(),
            'show_last_turn': set(ClientConfig.show_last_turn_keywords) if ClientConfig.show_last_turn_keywords else set(),
            'copy_result': set(ClientConfig.copy_result_keywords) if ClientConfig.copy_result_keywords else set(),
            'copy_all_context': set(ClientConfig.copy_all_context_keywords) if ClientConfig.copy_all_context_keywords else set(),
            'copy_current_role_context': set(ClientConfig.copy_current_role_context_keywords) if ClientConfig.copy_current_role_context_keywords else set(),
        }
        
        # 指令元数据
        command_definitions = {
            'clear_history': {
                'keywords': keyword_sets['clear_history'],
                'action': _execute_clear_history,
            },
            'revoke_last_turn': {
                'keywords': keyword_sets['revoke_last_turn'],
                'action': _execute_revoke_last_turn,
            },
            'show_last_turn': {
                'keywords': keyword_sets['show_last_turn'],
                'action': _execute_show_last_turn,
            },
            'copy_result': {
                'keywords': keyword_sets['copy_result'],
                'action': _execute_copy_result,
            },
            'copy_all_context': {
                'keywords': keyword_sets['copy_all_context'],
                'action': _execute_copy_all_context,
            },
            'copy_current_role_context': {
                'keywords': keyword_sets['copy_current_role_context'],
                'action': _execute_copy_current_role_context,
            },
        }

        # ======================================================================
        # --- 指令检测（单次查找，无嵌套 if-elif）---
        # ======================================================================
        
        # 检测指令关键词（使用集合快速查找）
        from util.client.ui import toast  # 提前导入 toast
        for cmd_name, cmd_def in command_definitions.items():
            if text in cmd_def['keywords']:
                cmd_def['action']()
                return None, COMMAND_TOKEN  # 返回指令标记

        # 检测角色前缀
        # 获取排序后的角色列表（使用缓存）
        roles = self._get_sorted_roles()

        for role_name, role_config in roles:
            # 合并检查：统一处理默认角色和未启用匹配的角色
            if role_name == RoleConfig.DEFAULT_ROLE_NAME or not role_config.match:
                continue

            # 检查前缀匹配
            if text.startswith(role_name):
                remaining_text = text[len(role_name):]
                remaining_text = remaining_text.lstrip(PREFIX_STRIP_PUNCTUATION).lstrip()

                # logger.debug(f"匹配到角色: {role_name}, 去除前缀后: {remaining_text[:50]}...")
                return role_config, remaining_text

        # 未匹配，使用默认角色
        default_role = self.role_loader.get_default_role()
        if default_role.process:
            # logger.debug(f"未匹配到角色前缀，使用默认角色，处理: {default_role.process}")
            return default_role, text

        # 未匹配到角色且默认角色不处理，返回原始文本
        # logger.debug("未匹配到角色且默认角色不处理，返回原始文本")
        return None, text
