"""
标点符号转换工具

根据前台应用判断是否需要转换全角标点为半角标点
"""

# 全角标点到半角标点的映射
FULL_TO_HALF = {
    '，': ', ',
    '。': '. ',
    '？': '? ',
    '！': '! ',
    '：': ': ',
    '；': '; ',
    '（': '(',
    '）': ')',
    '【': '[',
    '】': ']',
    '「': '"',
    '」': '"',
    '『': '\'',
    '』': '\'',
    '"': '"',
    '"': '"',
    "'" : "'",
    "'" : "'",
}


def convert_full_to_half(text: str) -> str:
    """
    将全角标点转换为半角标点

    Args:
        text: 待转换的文本

    Returns:
        转换后的文本
    """
    result = text
    for full, half in FULL_TO_HALF.items():
        result = result.replace(full, half)
    return result


def should_convert_punctuation(window_title: str, keywords: list) -> bool:
    """
    判断是否需要转换标点符号

    Args:
        window_title: 窗口标题
        keywords: 关键词列表（如 ['weixin', '微信']）

    Returns:
        True 表示需要转换
    """
    if not window_title:
        return False

    title_lower = window_title.lower()
    return any(keyword.lower() in title_lower for keyword in keywords)
