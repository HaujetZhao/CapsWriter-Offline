"""
LLM 角色加载器

功能：
1. 自动加载 LLM/ 目录下的所有角色
2. 从模块中提取角色配置
3. 错误处理和验证
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple


class RoleLoader:
    """角色加载器"""

    def __init__(self):
        self.roles_registry: Dict[str, dict] = {}
        self.llm_dir = Path(__file__).parent.parent / 'LLM'
        self.load_all_roles()

    def register_role(self, module_name: str, module):
        """从模块注册角色"""
        config_vars = {
            'name': '',
            'match': True,  # 是否启用前缀匹配（默认启用）
            'process': False,  # 是否启用 LLM 处理
            'provider': 'ollama',
            'api_url': '',  # API URL（直接使用完整 URL）
            'api_key': '',
            'model': '',
            'enable_hotwords': False,
            'enable_thinking': False,
            'enable_history': False,
            'max_context_length': 4096,
            'forget_duration': 600,
            'set_clipboard': False,  # 输出完成后是否复制到剪贴板
            'enable_clipboard_read': False,  # 是否启用剪贴板读取
            'clipboard_max_length': 1000,  # 剪贴板最大长度
            'output_mode': 'typing',  # 输出方式: 'typing' or 'toast'
            'toast_initial_width': 0.5,  # Toast 初始宽度
            'toast_initial_height': 0,  # Toast 初始高度（0 表示自动计算）
            'toast_font_size': 14,  # Toast 字体大小
            'toast_font_color': 'white',  # Toast 字体颜色
            'toast_bg_color': '#075077',  # Toast 背景颜色
            'toast_duration': 3000,  # Toast 显示时长（毫秒）
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

        # 空字符串和「默认」都表示默认角色
        role_name = config['name'] or '默认'
        if role_name == '默认':
            role_name = '默认'

        self.roles_registry[role_name] = {
            'module_name': module_name,
            **config,
        }

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

    def get_roles(self) -> Dict[str, dict]:
        """获取所有角色"""
        return self.roles_registry.copy()

    def get_default_role(self) -> dict:
        """获取默认角色"""
        return self.roles_registry.get('默认', {})

    def get_role_by_name(self, name: str) -> dict:
        """根据名字获取角色"""
        return self.roles_registry.get(name, {})

    def format_role_status(self, role_name: str, role_config: dict) -> str:
        """
        格式化角色状态显示

        Args:
            role_name: 角色名称
            role_config: 角色配置字典

        Returns:
            格式化的状态字符串
        """
        from rich.console import Console
        from rich.text import Text

        console = Console()
        text = Text()

        # 角色名称
        text.append(f"{role_name}：", style="bold cyan")

        # 匹配
        match = role_config.get('match', True)
        text.append("匹配 " if match else "匹配 ", style="green" if match else "dim")

        # 处理
        process = role_config.get('process', True)
        text.append("处理 " if process else "处理 ", style="green" if process else "dim")

        # 输出方式
        output_mode = role_config.get('output_mode', 'typing')
        if output_mode == 'typing':
            text.append("打字 ", style="green")
        elif output_mode == 'toast':
            text.append("弹窗 ", style="blue")
        else:
            text.append("打字 ", style="dim")

        # 思考
        thinking = role_config.get('enable_thinking', False)
        text.append("思考 " if thinking else "思考 ", style="green" if thinking else "dim")

        # 记忆
        history = role_config.get('enable_history', False)
        text.append("记忆 " if history else "记忆 ", style="green" if history else "dim")

        # 热词
        hotwords = role_config.get('enable_hotwords', False)
        text.append("热词 " if hotwords else "热词 ", style="green" if hotwords else "dim")

        # 剪贴板（读取）
        clipboard_read = role_config.get('enable_clipboard_read', False)
        text.append("剪贴板 " if clipboard_read else "剪贴板 ", style="green" if clipboard_read else "dim")

        # 模型信息
        model = role_config.get('model', '')
        provider = role_config.get('provider', '')
        text.append(f"  ({model} from {provider})", style="dim")

        # 渲染到字符串（禁用换行）
        with console.capture() as capture:
            console.print(text, overflow="ignore", no_wrap=False)
        return capture.get().strip()
