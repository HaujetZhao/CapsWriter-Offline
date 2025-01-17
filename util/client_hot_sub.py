from config import ClientConfig as Config
from util import hot_sub_en, hot_sub_rule, hot_sub_zh


def hot_sub(text: str) -> str:
    # 热词替换
    if Config.hot_zh:
        text = hot_sub_zh.热词替换(text)
    if Config.hot_en:
        text = hot_sub_en.热词替换(text)
    if Config.hot_rule:
        text = hot_sub_rule.热词替换(text)
    return text
