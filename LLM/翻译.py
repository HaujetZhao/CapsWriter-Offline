"""
翻译助手角色
"""

# ==================== 基本信息 ====================
# 角色名称（留空表示默认角色）
name = '翻译'

# 是否启用前缀匹配
match = True

# 是否启用 LLM 处理
process = True

# ==================== API 配置 ====================
# API 提供商: 'ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'claude', 'gemini'
# 用于当 api_url 为空时查找默认 api_url
provider = 'ollama'

# 如 http://localhost:11434/v1，留空则会自动使用 provider 对应的默认值
api_url = ''

# API Key（如果需要）
api_key = ''

# 模型名称
model = 'gemma3:4b'

# ==================== 功能配置 ====================
# 是否启用热词
enable_hotwords = False

# 是否启用思考（仅 Ollama）
enable_thinking = False

# 是否保留对话历史
enable_history = False

# ==================== 上下文管理 ====================
# 最大上下文长度（token 数）
max_context_length = 1000

# 遗忘时长（秒，0 表示不遗忘）
forget_duration = 0

# ==================== 输出配置 ====================
# 输出方式: 'typing' 直接打字输出, 'toast' 浮动窗口显示
output_mode = 'toast'

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
temperature = 0.7

# Top-p 采样（0-1，控制多样性）
top_p = 0.9

# 最大输出 token 数（0 表示使用模型默认值）
max_tokens = 512

# 停止序列（遇到这些词时停止生成，多个用逗号分隔）
# 例如：'###,END,完毕'
stop = ''

# ==================== 高级选项 ====================
# 额外的 API 参数（JSON 格式，高级用户使用）
# 例如：{'frequency_penalty': 0.5, 'presence_penalty': 0.5}
extra_options = {}

# ==================== System Prompt ====================
system_prompt = '''
你是一个翻译助手，将用户输入的文本翻译成英文。

要求：
- 只输出翻译结果，不要解释
- 保持原文的语气和风格
- 专业术语要准确翻译
- 不要添加任何额外说明
'''
