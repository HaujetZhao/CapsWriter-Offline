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
from util.llm_role_config import RoleConfig


class RoleLoader:
    """角色加载器"""

    def __init__(self):
        self.roles_registry: Dict[str, RoleConfig] = {}
        self.llm_dir = Path(__file__).parent.parent / 'LLM'
        self.load_all_roles()

    def register_role(self, module_name: str, module) -> str:
        """从模块注册角色

        Returns:
            角色名称
        """
        config_vars = {
            'name': '',
            'match': True,
            'process': False,
            'provider': 'ollama',
            'api_url': '',
            'api_key': '',
            'model': '',
            'enable_hotwords': False,
            'enable_thinking': False,
            'enable_history': False,
            'max_context_length': 4096,
            'forget_duration': 600,
            'set_clipboard': False,
            'enable_clipboard_read': False,
            'clipboard_max_length': 1000,
            'output_mode': 'typing',
            'toast_initial_width': 0.5,
            'toast_initial_height': 0,
            'toast_font_size': 14,
            'toast_font_color': 'white',
            'toast_bg_color': '#075077',
            'toast_duration': 3000,
            'temperature': 0.7,
            'top_p': 0.9,
            'max_tokens': 1024,
            'stop': '',
            'extra_options': {},
            'system_prompt': '',
        }

        config = {}
        for var_name, default_value in config_vars.items():
            if hasattr(module, var_name):
                config[var_name] = getattr(module, var_name)
            else:
                config[var_name] = default_value

        # 添加 module_name
        config['module_name'] = module_name

        # 创建 RoleConfig 对象
        role_config = RoleConfig.from_dict(config)

        # 空字符串和「默认」都表示默认角色
        role_name = role_config.name or '默认'
        if role_name == '默认':
            role_name = '默认'

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
        return self.roles_registry.get('默认', RoleConfig(name='默认', module_name='', process=False))

    def get_role_by_name(self, name: str) -> RoleConfig:
        """根据名字获取角色"""
        return self.roles_registry.get(name, RoleConfig(name='默认', module_name='', process=False))

    def format_role_status(self, role_name: str, role_config: RoleConfig):
        """
        格式化角色状态显示

        Args:
            role_name: 角色名称
            role_config: 角色配置（RoleConfig 对象）

        Returns:
            Text 对象（用于 Rich 渲染）
        """
        from rich.text import Text

        text = Text()

        # 角色名称
        text.append(f"{role_name}：", style="bold cyan")

        # 匹配
        match = role_config.match
        text.append("匹配 " if match else "匹配 ", style="green" if match else "dim")

        # 处理
        process = role_config.process
        text.append("处理 " if process else "处理 ", style="green" if process else "dim")

        # 输出方式
        output_mode = role_config.output_mode
        if output_mode == 'typing':
            text.append("打字 ", style="green")
        elif output_mode == 'toast':
            text.append("弹窗 ", style="blue")
        else:
            text.append("打字 ", style="dim")

        # 思考
        thinking = role_config.enable_thinking
        text.append("思考 " if thinking else "思考 ", style="green" if thinking else "dim")

        # 记忆
        history = role_config.enable_history
        text.append("记忆 " if history else "记忆 ", style="green" if history else "dim")

        # 热词
        hotwords = role_config.enable_hotwords
        text.append("热词 " if hotwords else "热词 ", style="green" if hotwords else "dim")

        # 剪贴板（读取）
        clipboard_read = role_config.enable_clipboard_read
        text.append("剪贴板 " if clipboard_read else "剪贴板 ", style="green" if clipboard_read else "dim")

        # 模型信息
        text.append(f"  ({role_config.model} from {role_config.provider})", style="dim")

        return text
