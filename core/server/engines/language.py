"""
ASR 引擎语言标识符映射

统一使用全称小写英文作为标准键（如 auto, chinese, english, japanese），
各引擎通过映射表转换为自身所需的标识符格式。

引擎标识符格式差异:
  - SenseVoice: 短代码 (auto/zh/en/ja/ko/yue)
  - Qwen3-ASR / ForceAligner: 英文明称首字母大写 (Chinese/English/Japanese/...)
  - FunASR-Nano: 中文文本 (中文/英文/日文/...)，非 MLT 版仅官方验证 3 语言
  - Paraformer: 不支持语言选择（中文专用模型）
"""

from typing import Dict, Optional, List

# ── 统一语言代码列表（按使用频率排序）──
# key 为统一代码（全称小写），各引擎子字典为该引擎的标识符

LANGUAGE_MAP: Dict[str, Dict[str, Optional[str]]] = {
    "auto": {                               # 自动检测
        "paraformer": None,
        "sensevoice": "auto",
        "fun_asr_nano": None,
        "qwen_asr": None,
        "aligner": None,
    },
    "chinese": {                            # 中文
        "paraformer": None,
        "sensevoice": "zh",
        "fun_asr_nano": "中文",
        "qwen_asr": "Chinese",
        "aligner": "Chinese",
    },
    "english": {                            # 英文
        "paraformer": None,
        "sensevoice": "en",
        "fun_asr_nano": "英文",
        "qwen_asr": "English",
        "aligner": "English",
    },
    "cantonese": {                          # 粤语
        "paraformer": None,
        "sensevoice": "yue",
        "fun_asr_nano": None, 
        "qwen_asr": "Cantonese",
        "aligner": "Cantonese",
    },
    "japanese": {                           # 日语
        "paraformer": None,
        "sensevoice": "ja",
        "fun_asr_nano": "日文",
        "qwen_asr": "Japanese",
        "aligner": "Japanese",
    },
    "korean": {                             # 韩语
        "paraformer": None,
        "sensevoice": "ko",
        "fun_asr_nano": None, 
        "qwen_asr": "Korean",
        "aligner": "Korean",
    },
    # ── Qwen3 额外支持的语言 ──
    # 注: FunASR 仅支持 中文/英文/日文，MLT 版支持更多语言

    "arabic": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Arabic",
        "aligner": "Arabic",
    },
    "german": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "German",
        "aligner": "German",
    },
    "french": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "French",
        "aligner": "French",
    },
    "spanish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Spanish",
        "aligner": "Spanish",
    },
    "portuguese": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Portuguese",
        "aligner": "Portuguese",
    },
    "indonesian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Indonesian",
        "aligner": "Indonesian",
    },
    "italian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Italian",
        "aligner": "Italian",
    },
    "russian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Russian",
        "aligner": "Russian",
    },
    "thai": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Thai",
        "aligner": "Thai",
    },
    "vietnamese": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Vietnamese",
        "aligner": "Vietnamese",
    },
    "turkish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Turkish",
        "aligner": "Turkish",
    },
    "hindi": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Hindi",
        "aligner": "Hindi",
    },
    "malay": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Malay",
        "aligner": "Malay",
    },
    "dutch": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Dutch",
        "aligner": "Dutch",
    },
    "swedish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Swedish",
        "aligner": "Swedish",
    },
    "danish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Danish",
        "aligner": "Danish",
    },
    "finnish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Finnish",
        "aligner": "Finnish",
    },
    "polish": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Polish",
        "aligner": "Polish",
    },
    "czech": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Czech",
        "aligner": "Czech",
    },
    "filipino": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Filipino",
        "aligner": "Filipino",
    },
    "persian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Persian",
        "aligner": "Persian",
    },
    "greek": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Greek",
        "aligner": "Greek",
    },
    "romanian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Romanian",
        "aligner": "Romanian",
    },
    "hungarian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Hungarian",
        "aligner": "Hungarian",
    },
    "macedonian": {
        "paraformer": None,
        "sensevoice": None,
        "fun_asr_nano": None,
        "qwen_asr": "Macedonian",
        "aligner": "Macedonian",
    },
}


# ── 引擎名称常量 ──

ENGINE_SENSEVOICE = "sensevoice"
ENGINE_QWEN_ASR = "qwen_asr"
ENGINE_FUN_ASR_NANO = "fun_asr_nano"
ENGINE_PARAFORMER = "paraformer"
ENGINE_ALIGNER = "aligner"

ALL_ENGINES = [ENGINE_PARAFORMER, ENGINE_SENSEVOICE, ENGINE_FUN_ASR_NANO, ENGINE_QWEN_ASR, ENGINE_ALIGNER]


# ── 工具函数 ──

def get_language(engine: str, unified_code: str) -> Optional[str]:
    """
    将统一语言代码转换为指定引擎的标识符。

    Args:
        engine: 引擎名称常量 (ENGINE_*)
        unified_code: 统一语言代码 (如 "chinese", "english")，不区分大小写

    Returns:
        引擎特定的语言标识符，若不支持则返回 None
    """
    entry = LANGUAGE_MAP.get(unified_code.lower())
    if entry is None:
        return None
    return entry.get(engine)


def supported_codes(engine: str) -> List[str]:
    """
    获取指定引擎支持的所有统一语言代码。

    Args:
        engine: 引擎名称常量

    Returns:
        支持的语言代码列表（按 LANGUAGE_MAP 定义顺序）
    """
    return [code for code, entry in LANGUAGE_MAP.items() if entry.get(engine) is not None]


def validate(engine: str, unified_code: str) -> bool:
    """
    验证指定引擎是否支持该语言代码。

    Returns:
        True 如果支持，False 否则
    """
    return get_language(engine, unified_code) is not None


def list_available() -> Dict[str, List[str]]:
    """
    列出所有引擎支持的语言代码概览。

    Returns:
        { engine_name: [supported_codes] }
    """
    return {engine: supported_codes(engine) for engine in ALL_ENGINES}
