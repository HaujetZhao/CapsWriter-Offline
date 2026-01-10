"""
LLM 常量配置

集中管理所有魔法数字、默认值和配置常量
"""

# ==================== 上下文管理常量 ====================
class ContextConstants:
    """上下文管理相关常量"""

    # Token 修剪阈值（使用 80% 阈值，保留 20% 给模型输出）
    TRIM_THRESHOLD_RATIO = 0.8

    # Token 估算常量
    CHARS_PER_TOKEN_CN = 1.5      # 中文字符：约 1.5 字符 = 1 token
    CHARS_PER_TOKEN_EN = 4.0      # 英文字符：约 4 字符 = 1 token

    # Unicode 中文字符范围
    CN_CHAR_START = '\u4e00'
    CN_CHAR_END = '\u9fff'


# ==================== RAG 常量 ====================
class RAGConstants:
    """热词 RAG 相关常量"""

    # 搜索参数
    DEFAULT_TOP_K = 5              # 默认返回前 5 个热词
    DEFAULT_THRESHOLD = 0.4        # 默认相似度阈值


# ==================== 文件监控常量 ====================
class WatcherConstants:
    """文件监控相关常量"""

    # 防抖延迟（秒）
    DEBOUNCE_DELAY = 3

    # 文件过滤
    PY_EXTENSION = '.py'
    INIT_FILE = '__init__.py'
    CACHE_DIR = '__pycache__'

    # 重载标记
    RELOAD_ALL_MARKER = '__reload_all__'


# ==================== 角色配置默认值 ====================
class RoleConfigDefaults:
    """角色配置的默认值"""

    # 基本配置
    DEFAULT_NAME = ''
    DEFAULT_MATCH = True
    DEFAULT_PROCESS = False

    # API 配置
    DEFAULT_PROVIDER = 'ollama'
    DEFAULT_API_URL = ''
    DEFAULT_API_KEY = ''
    DEFAULT_MODEL = 'gemma3:4b'

    # 上下文配置
    DEFAULT_MAX_CONTEXT_LENGTH = 4096
    DEFAULT_FORGET_DURATION = 600

    # 功能开关
    DEFAULT_ENABLE_HOTWORDS = False
    DEFAULT_ENABLE_THINKING = False
    DEFAULT_ENABLE_HISTORY = False
    DEFAULT_ENABLE_READ_SELECTION = False
    DEFAULT_SELECTION_MAX_LENGTH = 1000

    # 输出配置
    DEFAULT_OUTPUT_MODE = 'typing'
    DEFAULT_SET_CLIPBOARD = False

    # Toast 配置
    DEFAULT_TOAST_INITIAL_WIDTH = 0.5
    DEFAULT_TOAST_INITIAL_HEIGHT = 0
    DEFAULT_TOAST_FONT_FAMILY = ''
    DEFAULT_TOAST_FONT_SIZE = 14
    DEFAULT_TOAST_FONT_COLOR = 'white'
    DEFAULT_TOAST_BG_COLOR = '#075077'
    DEFAULT_TOAST_DURATION = 3000

    # 生成参数
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TOP_P = 0.9
    DEFAULT_MAX_TOKENS = 1024
    DEFAULT_STOP = ''

    # 默认角色名称
    DEFAULT_ROLE_NAME = '默认'


# ==================== API 配置 ====================
class APIConfig:
    """API 提供商配置"""

    # 默认 API URL
    DEFAULT_API_URLS = {
        'ollama': 'http://localhost:11434/v1',
        'openai': 'https://api.openai.com/v1',
        'deepseek': 'https://api.deepseek.com/v1',
        'moonshot': 'https://api.moonshot.cn/v1',
        'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
    }

    # 默认 API Keys
    DEFAULT_API_KEYS = {
        'ollama': 'ollama',
        'openai': '',
        'deepseek': '',
        'moonshot': '',
        'zhipu': '',
    }

    # 请求超时配置（秒）
    # 本地模型第一次可能需要载入，时间稍长
    # 超过10秒可以认为网络有问题
    DEFAULT_TIMEOUTS = {
        'ollama': 20.0,       # 本地模型
        'openai': 10.0,       # OpenAI API
        'deepseek': 10.0,     # DeepSeek API
        'moonshot': 10.0,     # Moonshot API
        'zhipu': 10.0,        # 智谱 API
        'claude': 10.0,       # Claude API
        'gemini': 10.0,       # Gemini API
    }

    # 默认超时（用于未列出的 provider）
    DEFAULT_TIMEOUT = 10.0


# ==================== Token 估算工具 ====================
def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    # 统计中文字符数量
    chinese_chars = sum(
        1 for c in text
        if ContextConstants.CN_CHAR_START <= c <= ContextConstants.CN_CHAR_END
    )

    # 统计非中文字符数量
    other_chars = len(text) - chinese_chars

    # 中文字符：约 1.5 字符 = 1 token
    # 英文和其他字符：约 4 字符 = 1 token
    tokens = int(
        chinese_chars / ContextConstants.CHARS_PER_TOKEN_CN +
        other_chars / ContextConstants.CHARS_PER_TOKEN_EN
    )

    return max(tokens, 1)  # 至少 1 个 token
