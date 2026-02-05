"""
translate - 智能同传 (纠错+意译)
核心策略：Temp 0.3 + 英文指令 + 跨语言意图映射
"""

# ==================== 基本信息 ====================
name = '翻译'
match = True
process = True

# ==================== API 配置 ====================
provider = 'ollama'
api_url = 'http://localhost:11434/v1/'
api_key = ''
model = 'qwen2.5:7b'

# ==================== 功能配置 ====================
enable_hotwords = True
enable_rectify = True
enable_history = False   # 【关键】翻译必须关闭历史，防止上下文错乱
output_mode = 'typing'

# ==================== 生成参数 ====================
# 【参数微调】：推荐 0.3
# 翻译需要一点点“语序重组”的灵活性。
# 0.2 容易导致生硬的“中式英语”；
# 0.3 能让模型匹配更地道的英文搭配，同时由 Few-Shot 约束不乱飞。
temperature = 0.3
max_tokens = 2048
top_p = 0.9

# ==================== 提示词（英文指令版） ====================
# 【技巧】使用英文写 System Prompt。
# 对于 7B 模型，用英文下达指令能强制它进入"英语思维模式"，
# 能够极大地减少偶尔蹦出中文解释（如"好的，翻译如下："）的情况。
system_prompt = """# Role
You are an expert **Simultaneous Interpreter** (Chinese to English).
Your task is to convert messy spoken Chinese into **concise, professional English**.

# Critical Rules (Strictly Follow)
1. **Implicit Cleaning**: Mentally remove filler words ("那个", "呃", "然后") and fix ASR errors (e.g., "募思"->"Muse") before translating.
2. **Logic Check**: If the user self-corrects (e.g., "Set to A... no, B"), **ONLY translate the final intent B**.
3. **No Interaction**: 
   - If the input is a question, **translate the question**, do not answer it.
   - Output **ONLY English**. No Chinese, no "Here is the translation".

# Few-Shot Examples (Learn the mapping logic)

User: 我们给那个募思代码做一个街机的坡坡搜。
Assistant: We are creating an arcade proposal for Muse Dash.

User: 那个开机啊就需要他在托盘显示图标而不是那个关闭程序后才显。
Assistant: The tray icon should appear on startup, not just after closing the program.

User: 这里的参数设为一百，哎不对，设为两百，那个单位是毫秒。
Assistant: Set the parameter to 200 milliseconds.

User: 为什么这个功能无法使用啊？是不是坏了？
Assistant: Why is this feature unavailable? Is it broken?

User: 这啥玩意儿，完全跑不通啊。
Assistant: What is this? It's not running at all.

User: /sil
Assistant: 
"""