from config import ClientConfig as Config
from util.tools import hot_sub_en
from util.tools import hot_sub_zh
from util.tools import hot_sub_rule
from util.logger import get_logger

# 获取日志记录器
logger = get_logger('client')


def hot_sub(text: str) -> str:
    original = text

    # 热词替换
    if Config.hot_zh:
        text = hot_sub_zh.热词替换(text)
    if Config.hot_en:
        text = hot_sub_en.热词替换(text)
    if Config.hot_rule:
        text = hot_sub_rule.热词替换(text)

    # 只有当文本发生变化时才记录日志
    if text != original:
        logger.debug(f"热词替换: '{original[:30]}...' -> '{text[:30]}...'")

    return text
