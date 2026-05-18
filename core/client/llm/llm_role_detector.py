"""
LLM 角色检测器

功能：
1. 检测文本是否匹配某个角色前缀
2. 返回对应的角色配置和去除前缀后的文本
"""
from typing import Tuple, Optional
from .llm_role_config import RoleConfig
from .llm_interfaces import IRoleLoader
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
            if role_name in ['默认', 'default', '']:
                continue

            # 检查角色是否启用
            if not role_config.enabled:
                continue

            # 遍历显示名和所有别名
            for name in role_config.names:
                if not name:
                    continue
                if text.startswith(name):
                    remaining_text = text[len(name):]
                    remaining_text = remaining_text.lstrip('：，。,. ')
                    return role_config, remaining_text

        # 未匹配，使用默认角色
        default_role = self.role_loader.get_default_role()
        if default_role.enabled:
            # logger.debug(f"未匹配到角色前缀，使用默认角色")
            return default_role, text

        # logger.debug("未匹配到角色且默认角色未启用，返回原始文本")
        return None, text
