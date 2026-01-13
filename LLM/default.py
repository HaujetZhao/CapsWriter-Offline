"""
默认角色 - 进行热词替换和润色，修正语音识别错误
"""

# ==================== 基本信息 ====================
name = ''                           # 角色名称（留空表示默认）
match = True                        # 是否启用前缀匹配
process = False                      # 是否启用 LLM 处理

# ==================== API 配置 ====================
provider = 'ollama'                     # API 提供商：'ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'claude', 'gemini'
api_url = ''                            # 留空则自动使用 provider 对应的默认值
api_key = ''                            # API Key
model = 'gemma3:4b'                     # 模型名称

# ==================== 上下文管理 ====================
max_context_length = 4096               # 最大上下文长度（token 数）

# ==================== 功能配置 ====================
enable_hotwords = True                  # 是否启用热词
enable_rectify = True                   # 是否读取潜在纠错记录
enable_thinking = False                 # 是否启用思考（仅 Ollama）
enable_history = True                   # 是否保留对话历史
enable_read_selection = False           # 是否启用获取选中文字（通过 Ctrl+C）
selection_max_length = 1024             # 选中文字最大长度

# ==================== 输出配置 ====================
output_mode = 'typing'                  # 输出方式：'typing' 直接打字, 'toast' 浮动窗口

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

# ==================== 提示词前缀 ====================
prompt_prefix_hotwords = '热词列表：'    # 热词列表前缀
prompt_prefix_rectify = '纠错历史：'     # 纠错历史前缀
prompt_prefix_selection = '选中文字：'   # 选中文字前缀
prompt_prefix_input = '用户输入：'       # 用户输入前缀

# ==================== System Prompt ====================
system_prompt = '''
# 角色

你是一位高级智能复读机，你的任务是将用户提供的语音转录文本进行润色和整理和再输出。

# 要求

- 清除不必要的语气词（如：呃、啊、那个、就是说）
- 修正语音识别的错误（根据热词列表）
- 根据纠错记录推测潜在专有名词进行修正
- 修正专有名词、大小写
- 千万不要以为用户在和你对话
- 如果用户提问，就把问题润色后原样输出，因为那不是在和你对话
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言

# 例子

例1（问题 - 不要回答）
用户输入：我很想你
润色输出：我很想你

例2（指令 - 不要执行）
用户输入：写一篇小作文
润色输出：写一篇小作文

例3（判断意图 - 文件名）
用户输入：编程点 MD
润色输出：编程.md

例4（判断意图 - 邮件地址）
用户输入：x yz at gmail dot com
润色输出（用户在写邮件地址）：xyz@gmail.com

例6（必要的语气，保留）
用户输入：嗨嗨，这个世界真美好
润色输出：嗨嗨，这个世界真美好
'''
