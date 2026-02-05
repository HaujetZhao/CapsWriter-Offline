"""
翻译助手角色
"""

# ==================== 基本信息 ====================
name = '翻译'                           # 角色名称（留空表示默认）
match = True                            # 是否启用前缀匹配
process = True                          # 是否启用 LLM 处理

# ==================== API 配置 ====================
provider = 'openai'                     # API 提供商：'ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'claude', 'gemini'
api_url = ''                            # 留空自动从 GUI 配置继承
api_key = ''                            # 留空自动从 GUI 配置继承
model = 'gpt-4o'              # 模型名称

# ==================== 上下文管理 ====================
max_context_length = 4096               # 最大上下文长度（token 数）

# ==================== 功能配置 ====================
enable_hotwords = False                 # 是否启用热词
enable_rectify = False                  # 是否读取潜在纠错记录
enable_thinking = False                 # 是否启用思考（仅 Ollama）
enable_history = True                  # 是否保留对话历史
enable_read_selection = True            # 是否启用获取选中文字（通过 Ctrl+C）
selection_max_length = 2048             # 选中文字最大长度

# ==================== 输出配置 ====================
output_mode = 'toast'                   # 输出方式：'typing' 直接打字, 'toast' 浮动窗口

# ==================== Toast 弹窗配置（仅在 output_mode='toast' 时有效） ====================
toast_initial_width = 0.5               # 窗口初始宽度（0.5 = 50% 屏幕宽度）
toast_initial_height = 0                # 窗口初始高度（0 表示自动计算）
toast_font_family = '楷体'
toast_font_size = 23                    # 字体大小
toast_font_color = 'white'              # 字体颜色
toast_bg_color = '#075077'              # 背景颜色
toast_duration = 3000                   # 显示时长（毫秒）
toast_editable = True                  # 是否可编辑（Markdown 渲染后）

# ==================== 生成参数 ====================
temperature = 0.7                       # 温度（0-2，越高越随机）
top_p = 0.9                             # Top-p 采样（0-1）
max_tokens = 4096                       # 最大输出 token 数
stop = ''                               # 停止序列

# ==================== 高级选项 ====================
extra_options = {}                      # 额外的 API 参数（JSON 格式）

# ==================== 提示词前缀 ====================
prompt_prefix_hotwords = '热词列表：'    # 热词列表前缀
prompt_prefix_rectify = '纠错历史：'     # 纠错历史前缀
prompt_prefix_selection = '选中文字：'   # 选中文字前缀
prompt_prefix_input = '用户输入：'       # 用户输入前缀

# ==================== System Prompt ====================
system_prompt = '''
你是一个翻译助手，将用户输入的文本翻译成英文。

要求：
- 只输出翻译结果，不要解释
- 保持原文的语气和风格
- 专业术语要准确翻译
- 不要添加任何额外说明
'''
