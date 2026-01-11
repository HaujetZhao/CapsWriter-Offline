"""
LLM 角色模块 - 仅用于角色配置

此文件夹只存放角色配置文件，不要放其他 Python 文件
"""

# 此文件为空，仅用于标识 LLM 为 Python 包，请勿删除本文件



"""
# 角色配置模板

# 基本信息
name: str = ""                               # 角色显示名称
match: bool = True                           # 是否启用前缀匹配
process: bool = True                         # 是否启用 LLM 处理

# API 配置
provider: str = 'ollama'                     # API 提供商
api_url: str = ''                            # API 地址
api_key: str = ''                            # API Key
model: str = 'gemma3:4b'                     # 模型名称

# 上下文管理
max_context_length: int = 4096               # 最大上下文长度（token 数）
forget_duration: int = 0                     # 遗忘时长（秒，0 表示不遗忘）

# 功能配置
enable_thinking: bool = False                # 是否启用思考（仅 Ollama 支持）
enable_history: bool = False                 # 是否保留对话历史
enable_hotwords: bool = False                # 是否读取潜在热词列表
enable_rectify: bool = False                 # 是否读取潜在纠错记录
enable_read_selection: bool = False          # 是否读取鼠标所选文字（通过 Ctrl+C）
selection_max_length: int = 1000             # 选中文字最大长度

# 输出配置
output_mode: str = 'typing'                  # 输出方式: 'typing' 或 'toast' (即打字输出或弹窗输出)
set_clipboard: bool = False                  # 输出完成后是否复制到剪贴板

# Toast 弹窗配置
toast_initial_width: float = 0.5             # Toast 窗口初始宽度（0.5 = 50% 屏幕宽度）
toast_initial_height: int = 0                # Toast 窗口初始高度（0 表示自动计算）
toast_font_family: str = ''                  # Toast 字体（空字符串表示使用系统默认）
toast_font_size: int = 16                    # Toast 字体大小
toast_font_color: str = 'white'              # Toast 字体颜色
toast_bg_color: str = '#075077'              # Toast 背景颜色
toast_duration: int = 3000                   # Toast 显示时长（毫秒）

# 生成参数
temperature: float = 0.7                     # 温度（0-2）
top_p: float = 0.9                           # Top-p 采样
max_tokens: int = 1024                       # 最大输出 token 数（0 表示使用模型默认值）
stop: str = ''                               # 停止序列

# 高级选项
extra_options: Dict[str, Any] = field(default_factory=dict)  # 额外的 API 参数

# System Prompt
system_prompt: str = ''                      # 系统提示词


"""