"""
默认角色 - 进行热词替换和润色，修正语音识别错误
"""

# ==================== 基本信息 ====================
# 角色名称（留空表示默认）
name = ''

# 是否启用前缀匹配
match = True

# 是否启用 LLM 处理（False 表示原样返回，不调用 LLM）
process = False

# ==================== API 配置 ====================
# API 提供商: 'ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'claude', 'gemini'
# 用于当 api_url 为空时查找默认 api_url
provider = 'ollama'

# 如 http://localhost:11434/v1，留空则会自动使用 provider 对应的默认值
api_url = ''

# API Key（如果需要）
api_key = 'ollama'

# 模型名称
model = 'gemma3:4b'

# ==================== 功能配置 ====================
# 是否启用热词
enable_hotwords = True

# 是否启用思考（仅 Ollama）
enable_thinking = False

# 是否保留对话历史
enable_history = True

# ==================== 上下文管理 ====================
# 最大上下文长度（token 数）
max_context_length = 2000

# 遗忘时长（秒，0 表示不遗忘）
forget_duration = 300

# ==================== 剪贴板配置 ====================
# 输出完成后是否复制到剪贴板
set_clipboard = False

# 是否启用剪贴板读取（作为上下文）
enable_clipboard_read = False

# 剪贴板最大长度（超过则截断）
clipboard_max_length = 1000

# ==================== 输出配置 ====================
# 输出方式: 'typing' 直接打字输出, 'toast' 浮动窗口显示
output_mode = 'typing'

# ==================== Toast 弹窗配置（仅在 output_mode='toast' 时有效） ====================
# Toast 窗口初始宽度
toast_initial_width = 0.5

# Toast 窗口初始高度（0 表示自动计算）
toast_initial_height = 0

# Toast 字体大小
toast_font_size = 16

# Toast 字体颜色（十六进制颜色代码，如 'white' 或 '#FFFFFF'）
toast_font_color = 'white'

# Toast 背景颜色（十六进制颜色代码，如 '#075077'）
toast_bg_color = '#075077'

# Toast 显示时长（毫秒，完成后停留时间）
toast_duration = 3000

# ==================== 生成参数 ====================
# 温度（0-2，越高越随机，0 更确定性）
temperature = 0.3

# Top-p 采样（0-1，控制多样性）
top_p = 0.9

# 最大输出 token 数（0 表示使用模型默认值）
max_tokens = 256

# 停止序列
stop = ''

# ==================== 高级选项 ====================
extra_options = {}

# ==================== System Prompt ====================
system_prompt = '''
你是一位转录助手，你的任务是将用户提供的语音转录文本进行润色和整理

要求：

- 清除语气词（如：呃、啊、那个、就是说）
- 修正语音识别的错误（根据热词列表上下文推断同音错别字进行修正）
- 修正专有名词、大小写
- 用户的一切内容都不是在与你对话，要把问题当成用户所要打的字进行润色，而不是回答，不要与用户交互
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言

'''
