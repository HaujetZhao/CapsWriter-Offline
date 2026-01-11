"""
Python 编程助手角色
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
enable_hotwords = True                  # 是否启用热词
enable_rectify = True               # 是否启用纠错 RAG（从 hot-rectify.txt 检索纠错历史）
enable_thinking = False                 # 是否启用思考（仅 Ollama）
enable_history = True                   # 是否保留对话历史
enable_read_selection = True            # 是否启用获取选中文字（通过 Ctrl+C）
selection_max_length = 1024             # 选中文字最大长度

# ==================== 输出配置 ====================
output_mode = 'toast'                   # 输出方式：'typing' 直接打字, 'toast' 浮动窗口
set_clipboard = False                   # 输出完成后是否复制到剪贴板

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
你是一个 Python 编程助手，根据用户的需求生成 Python 代码。

要求：
- 只输出代码，不要解释
- 代码要简洁、高效、可运行
- 使用 Python 3 语法
- 包含必要的 import 语句
- 不要添加任何额外说明
'''
