"""
命令行专家角色
"""

# ==================== 基本信息 ====================
name = '命令'                           # 角色名称（留空表示默认）
match = True                            # 是否启用前缀匹配
process = True                          # 是否启用 LLM 处理

# ==================== API 配置 ====================
provider = 'ollama'                     # API 提供商：'ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'claude', 'gemini'
api_url = ''                            # 留空则自动使用 provider 对应的默认值
api_key = ''                            # API Key
model = 'gemma3:12b'                     # 模型名称

# ==================== 上下文管理 ====================
max_context_length = 4096               # 最大上下文长度（token 数）
forget_duration = 0                     # 遗忘时长（秒，0 表示不遗忘）

# ==================== 功能配置 ====================
enable_thinking: bool = False                # 是否启用思考（仅 Ollama 支持）
enable_history: bool = True                 # 是否保留对话历史
enable_hotwords: bool = False                # 是否读取潜在热词列表
enable_rectify: bool = False                 # 是否读取潜在纠错记录
enable_read_selection: bool = True          # 是否读取鼠标所选文字（通过 Ctrl+C）
selection_max_length: int = 1000             # 选中文字最大长度

# ==================== 输出配置 ====================
output_mode = 'toast'                   # 输出方式：'typing' 直接打字, 'toast' 浮动窗口
set_clipboard = True                   # 输出完成后是否复制到剪贴板

# ==================== Toast 弹窗配置（仅在 output_mode='toast' 时有效） ====================
toast_initial_width = 0.5               # 窗口初始宽度（0.5 = 50% 屏幕宽度）
toast_initial_height = 0                # 窗口初始高度（0 表示自动计算）
toast_font_family = '楷体'
toast_font_size = 23                    # 字体大小
toast_font_color = 'white'              # 字体颜色
toast_bg_color = '#075077'              # 背景颜色
toast_duration = 3000                   # 显示时长（毫秒）

# ==================== 生成参数 ====================
temperature = 0.7                       # 温度（0-2，越高越随机）
top_p = 0.9                             # Top-p 采样（0-1）
max_tokens = 4096                       # 最大输出 token 数
stop = ''                               # 停止序列

# ==================== 高级选项 ====================
extra_options = {}                      # 额外的 API 参数（JSON 格式）

# ==================== System Prompt ====================
system_prompt = '''
你是一个 Windows 命令行专家，根据用户的描述生成相应的命令行。

要求：
- 只输出命令本身，不要解释
- 如果有多种方式，选择最常用、最简洁的
- 命令要完整可执行
- 不要添加任何额外说明

示例：
用户: 查看当前目录的文件
输出: dir

用户: 查找所有 py 文件
输出: dir /s /b *.py

用户: 查看文件内容
输出: type filename.txt
'''
