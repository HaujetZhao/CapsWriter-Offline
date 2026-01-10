"""
LLM 角色信息格式化器

功能：
1. 格式化角色状态显示
2. 提供统一的 Rich 渲染支持
"""
from rich.text import Text
from rich.console import Console
from util.llm.llm_role_config import RoleConfig


class RoleFormatter:
    """角色信息格式化器 - 负责角色显示的格式化"""

    @staticmethod
    def format_status(role_name: str, role_config: RoleConfig) -> Text:
        """
        格式化角色状态显示

        Args:
            role_name: 角色名称
            role_config: 角色配置（RoleConfig 对象）

        Returns:
            Text 对象（用于 Rich 渲染）
        """
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

        # 读取选中文字
        read_selection = role_config.enable_read_selection
        text.append("读选区 " if read_selection else "读选区 ", style="green" if read_selection else "dim")

        # 模型信息
        text.append(f"  ({role_config.model} from {role_config.provider})", style="dim")

        return text

    @staticmethod
    def print_status(role_name: str, role_config: RoleConfig, prefix: str = "  "):
        """
        打印角色状态（带前缀）

        Args:
            role_name: 角色名称
            role_config: 角色配置
            prefix: 前缀文本（默认两个空格）
        """
        console = Console()
        status_line = RoleFormatter.format_status(role_name, role_config)

        text = Text(prefix)
        text.append(status_line)
        console.print(text)

    @staticmethod
    def print_update(role_name: str, role_config: RoleConfig):
        """
        打印角色更新信息

        Args:
            role_name: 角色名称
            role_config: 角色配置
        """
        console = Console()
        status_line = RoleFormatter.format_status(role_name, role_config)

        # 构建 "角色更新  " 前缀 + 状态行
        prefix = Text("\n角色更新  ")
        prefix.append(status_line)
        console.print(prefix + "\n")
