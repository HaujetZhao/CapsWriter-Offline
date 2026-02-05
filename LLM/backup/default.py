"""
direct - 直接输出，不经过 LLM 处理
这是默认角色，无需任何前缀
"""

# ==================== 基本信息 ====================
name = ''                               # 留空 = 默认角色
match = True
process = False                         # 关闭 LLM 处理，直接输出 ASR 结果

# ==================== 其他配置保持默认 ====================
provider = 'openai'
api_url = ''
api_key = ''
model = ''

enable_hotwords = True
enable_rectify = True
output_mode = 'typing'
