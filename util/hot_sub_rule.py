"""
# 规则是每行一条的文本，左边是正则规则，右边是替换词，将中间用带空格的等号隔开，文本两边的空格会被省略。
# 导入模块后，先更新热词词典，然后再替换句子中的热词。

使用方法示例：
see the __main__ part
"""

import re

__all__ = ["update_trending_words_dict", "replace_trending_words"]

pattern_dict = dict[str, str]()


def update_trending_words_dict(trending_words_text: str) -> int:
    """
    把热词规则文本中的每一行用 = 分开，去除多余空格后添加到热词词典，
    key     是被替换的词，
    value   是将被替换成的词
    """
    global pattern_dict  # pylint: disable=global-variable-not-assigned
    pattern_dict.clear()
    for trending_word in trending_words_text.splitlines():
        if not trending_word or trending_word.startswith("#"):
            continue
        key_value = trending_word.split(" = ")
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip()
            pattern_dict[key] = value
    return len(pattern_dict)


def match_trending_words(sentence: str) -> list[str]:
    """
    将全局「热词词典」中的热词按照 key 依次与句子匹配，将所有匹配到的热词放到列表
    """
    global pattern_dict  # pylint: disable=global-variable-not-assigned

    all_matches: list[str] = []
    for pattern in pattern_dict:
        if re.findall(pattern, sentence):
            all_matches.append(pattern)

    return all_matches


def replace_trending_words(sentence: str) -> str:
    """
    从热词词典中查找匹配的热词，替换句子

    句子：       被查找和替换的句子
    """
    all_match_patterns = match_trending_words(sentence)
    for pattern in all_match_patterns:
        sentence = re.sub(pattern, pattern_dict[pattern], sentence)
    return sentence


if __name__ == "__main__":
    print("\x9b42m-------------开始---------------")

    TRENDING_WORDS_TEXT = """
        毫安时  =  mAh
        伏特   =   V
        赫兹   =   Hz
    """

    update_trending_words_dict(TRENDING_WORDS_TEXT)

    res = replace_trending_words("这款手机有5000毫安时的大电池")
    print(f"{res}")
    replace_trending_words(
        "国内交流电一般是50赫兹"
    )  # 输出：国内交流电一般是50Hz
    print(f"{res}")
