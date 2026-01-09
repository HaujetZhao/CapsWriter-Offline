"""
LLM 角色配置 Dataclass

使用 Dataclass 替代字典，提供类型安全和更好的 IDE 支持
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RoleConfig:
    """角色配置

    包含单个角色的所有配置信息
    """
    # 基本信息
    name: str                                    # 角色显示名称
    module_name: str                             # 模块名称（如 "LLM.翻译"）
    match: bool = True                           # 是否启用前缀匹配
    process: bool = True                         # 是否启用 LLM 处理

    # API 配置
    provider: str = 'ollama'                     # API 提供商
    api_url: str = ''                            # API 地址
    api_key: str = ''                            # API Key

    # 模型配置
    model: str = 'gemma3:4b'                     # 模型名称

    # 功能配置
    enable_hotwords: bool = False                # 是否启用热词
    enable_thinking: bool = False                # 是否启用思考（仅 Ollama）
    enable_history: bool = False                 # 是否保留对话历史

    # 上下文管理
    max_context_length: int = 2000               # 最大上下文长度（token 数）
    forget_duration: int = 300                   # 遗忘时长（秒，0 表示不遗忘）

    # 输出配置
    output_mode: str = 'typing'                  # 输出方式: 'typing' 或 'toast'

    # Toast 弹窗配置
    toast_initial_width: float = 0.5             # Toast 窗口初始宽度（0.5 = 50% 屏幕宽度）
    toast_initial_height: int = 0                # Toast 窗口初始高度（0 表示自动计算）
    toast_font_size: int = 16                    # Toast 字体大小
    toast_font_color: str = 'white'              # Toast 字体颜色
    toast_bg_color: str = '#075077'              # Toast 背景颜色
    toast_duration: int = 3000                   # Toast 显示时长（毫秒）

    # 剪贴板配置
    enable_clipboard_read: bool = False          # 是否启用剪贴板读取
    clipboard_max_length: int = 1000             # 剪贴板最大长度
    set_clipboard: bool = False                  # 输出完成后是否复制到剪贴板

    # 生成参数
    temperature: float = 0.7                     # 温度（0-2）
    top_p: float = 0.9                           # Top-p 采样
    max_tokens: int = 1024                       # 最大输出 token 数（0 表示使用模型默认值）
    stop: str = ''                               # 停止序列

    # 高级选项
    extra_options: Dict[str, Any] = field(default_factory=dict)  # 额外的 API 参数

    # System Prompt
    system_prompt: str = ''                      # 系统提示词

    def get(self, key: str, default=None):
        """兼容字典的 get 方法

        用于平滑过渡到 Dataclass
        """
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        用于需要字典格式的场景
        """
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleConfig':
        """从字典创建 RoleConfig

        Args:
            data: 包含角色配置的字典

        Returns:
            RoleConfig 对象
        """
        # 过滤掉不在 dataclass 中的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # 设置默认值
        defaults = {
            'name': '默认',
            'module_name': '',
            'match': True,
            'process': True,
            'provider': 'ollama',
            'model': 'gemma3:4b',
            'enable_hotwords': False,
            'enable_thinking': False,
            'enable_history': False,
            'max_context_length': 2000,
            'forget_duration': 300,
            'output_mode': 'typing',
            'temperature': 0.7,
            'top_p': 0.9,
            'max_tokens': 1024,
            'system_prompt': '',
        }

        # 合并默认值和用户配置
        for key, value in defaults.items():
            if key not in filtered_data:
                filtered_data[key] = value

        return cls(**filtered_data)
