"""
LLM 角色检测器

功能：
1. 检测文本是否匹配某个角色前缀
2. 返回对应的角色配置和去除前缀后的文本
"""
from typing import Tuple, Optional
from util.llm.llm_role_config import RoleConfig
from util.llm.llm_interfaces import IRoleLoader
from . import logger


class RoleDetector:
    """角色检测器 - 负责从输入文本中检测角色"""

    def __init__(self, role_loader: IRoleLoader):
        """
        Args:
            role_loader: 角色加载器实例
        """
        self.role_loader = role_loader

    def detect(self, text: str) -> Tuple[Optional[RoleConfig], str]:
        """
        检测文本是否匹配某个角色前缀

        Args:
            text: 输入文本

        Returns:
            (role_config, content) - role_config 是 RoleConfig 对象，
            content 是去除前缀后的文本
        """
        # logger.debug(f"检测角色，输入文本: {text[:50]}...")

        for role_name, role_config in self.role_loader.get_roles().items():
            if role_name == '默认':
                continue

            # 检查是否启用前缀匹配
            if not role_config.match:
                continue

            name = role_config.name
            # 空名字和「默认」都不作为前缀匹配
            if not name or name == '默认':
                continue

            if name and text.startswith(name):
                remaining_text = text[len(name):]
                remaining_text = remaining_text.lstrip('：，。,. ')

                # logger.debug(f"匹配到角色: {name}, 去除前缀后: {remaining_text[:50]}...")
                return role_config, remaining_text

        # 未匹配，使用默认角色
        default_role = self.role_loader.get_default_role()
        if default_role.process:
            # logger.debug(f"未匹配到角色前缀，使用默认角色，处理: {default_role.process}")
            return default_role, text

        # logger.debug("未匹配到角色且默认角色不处理，返回原始文本")
        return None, text
