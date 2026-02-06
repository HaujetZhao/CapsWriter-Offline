"""
LLM 角色加载器

功能：
1. 自动加载 LLM/ 目录下的所有角色
2. 从模块中提取角色配置
3. 错误处理和验证
"""

import sys
from pathlib import Path
from typing import Dict
from util.llm.llm_role_config import RoleConfig


class RoleLoader:
    """角色加载器"""

    def __init__(self):
        self.roles_registry: Dict[str, RoleConfig] = {}
        from config_client import BASE_DIR
        self.llm_dir = Path(BASE_DIR) / 'LLM'
        self.load_all_roles()

    def register_role(self, module_name: str, module) -> str:
        """从模块注册角色

        Returns:
            角色名称
        """
        from dataclasses import fields
        
        # 1. 自动从 RoleConfig 获取所有的命名字段
        config = {'module_name': module_name}
        for f in fields(RoleConfig):
            if f.name == 'module_name':
                continue
            # 如果模块（角色脚本）里定义了这个变量，就读取它
            if hasattr(module, f.name):
                config[f.name] = getattr(module, f.name)
            # 否则不设置，让 RoleConfig 自动使用 dataclass 的默认值

        # 2. 创建 RoleConfig 对象
        role_config = RoleConfig(**config)

        # 空字符串和「默认」都表示默认角色
        role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME

        self.roles_registry[role_name] = role_config

        return role_name

    def load_all_roles(self):
        """加载所有角色"""
        self.roles_registry.clear()
        errors = []

        for file_path in sorted(self.llm_dir.glob('*.py')):
            if file_path.name == '__init__.py':
                continue

            try:
                module_name = f"LLM.{file_path.stem}"

                if module_name in sys.modules:
                    del sys.modules[module_name]

                module = __import__(module_name, fromlist=[''])

                if not hasattr(module, 'provider') or not hasattr(module, 'model'):
                    errors.append({
                        'file': file_path.name,
                        'error': '缺少必需字段',
                        'details': '缺少 provider 或 model'
                    })
                    continue

                self.register_role(module_name, module)

            except SyntaxError as e:
                errors.append({
                    'file': file_path.name,
                    'error': '语法错误',
                    'details': f"第 {e.lineno} 行: {e.msg}"
                })
            except Exception as e:
                errors.append({
                    'file': file_path.name,
                    'error': type(e).__name__,
                    'details': str(e)
                })

        return errors

    def reload_role(self, file_path: str):
        """重新加载单个角色"""
        try:
            file_path = Path(file_path)

            if file_path.suffix != '.py' or file_path.name == '__init__.py':
                return False, "不是角色文件"

            module_name = f"LLM.{file_path.stem}"

            if module_name in sys.modules:
                del sys.modules[module_name]

            module = __import__(module_name, fromlist=[''])

            if not hasattr(module, 'provider') or not hasattr(module, 'model'):
                return False, "缺少必需字段"

            self.register_role(module_name, module)

            return True, None

        except SyntaxError as e:
            return False, f"语法错误 (第 {e.lineno} 行): {e.msg}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)}"

    def get_roles(self) -> Dict[str, RoleConfig]:
        """获取所有角色"""
        return self.roles_registry.copy()

    def get_default_role(self) -> RoleConfig:
        """获取默认角色"""
        return self.roles_registry.get(RoleConfig.DEFAULT_ROLE_NAME, RoleConfig(name=RoleConfig.DEFAULT_ROLE_NAME, module_name='', process=False))

    def get_role_by_name(self, name: str) -> RoleConfig:
        """根据名字获取角色"""
        return self.roles_registry.get(name, RoleConfig(name=RoleConfig.DEFAULT_ROLE_NAME, module_name='', process=False))
