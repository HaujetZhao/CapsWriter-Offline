from time import time

from pypinyin import pinyin

'''
热词是每行一个的文本，先更新热词词典，然后再替换句子中的热词。
使用方法示例：


热词文本 = """
    撒贝宁
    康辉
    周涛
    李嘉懿
"""

更新热词词典(热词文本)

res = replace_trending_words('我有个同学叫李佳一')

print(res)

'''


__all__ = [
    "update_trending_words_dict",
    "replace_trending_words",
    "polyphonic_characters",
    "tones",
]


# ================全局配置=======================


trending_words_dict = {}
polyphonic_characters = True
tones = False  # 是否要求匹配声调


# ===========================================


style = 1 if tones else 0  # 依据是否需要声调，设置拼音风格


def update_trending_words_dict(trending_words_text: str):
    """
    将一行一个热词的文本转换为拼音词典
    以 # 开头会被省略

    heteronym: 是否启用多音字

    如果启用了多音字，返回的词典是这样的形式：
        {'撒贝宁': [
                    ['sā', 'bèi', 'níng'],
                    ['sǎ', 'bèi', 'níng'],
                    ['sā', 'bèi', 'nìng'],
                    ['sǎ', 'bèi', 'nìng'],
                    ['sā', 'bèi', 'zhù'],
                    ['sǎ', 'bèi', 'zhù']
                ]
        }

    如果没有启用多音字，返回的词典是这样的形式：
        {'撒贝宁': [
                    ['sā', 'bèi', 'níng'],
                ]
        }
    """
    global trending_words_dict
    trending_words_dict.clear()
    for word in trending_words_text.splitlines():
        word = word.strip()  # 给热词去掉多余的空格
        if not word or word.startswith("#"):
            continue  # 过滤掉注释
        word_pinyin = pinyin(word, style, polyphonic_characters)  # 得到拼音

        if len(word_pinyin) != len(word):
            print(f"\x9b31m    热词「{word}」得到的拼音数量与字数不符，抛弃\x9b0m")
            continue

        pinyin_list = [
            [],
        ]
        for polyphonic in word_pinyin:
            num_sounds = len(polyphonic)
            if num_sounds > 1:
                original_list, pinyin_list = pinyin_list, []
                for sound in polyphonic:
                    pinyin_list.extend([x.copy() + [sound] for x in original_list])
            else:
                for x in pinyin_list:
                    x.append(polyphonic[0])

        trending_words_dict[word] = pinyin_list
    return len(trending_words_dict)


def match_trending_words(sentence: str):
    """
    将全局「热词词典」中的热词按照拼音依次与句子匹配，将所有匹配到的「热词、拼音」以元组放到列表
    将列表返回
    """
    global trending_words_dict

    all_matches = []
    sentence_pinyin = "".join(
        [x[0] for x in pinyin(sentence, style, polyphonic_characters)]
    )  # 字符串形式的句子拼音
    for word in trending_words_dict.keys():
        for pinyin_sequence in trending_words_dict[word]:
            if "".join(pinyin_sequence) in sentence_pinyin:
                all_matches.append((word, pinyin_sequence))
            else:
                continue
    return all_matches


def get_pinyin_index(sentence: str):
    """
    输入句子字符串，获取一个列表，列表内是字典，字典包含了拼音和索引

    例如，输入 '撒贝宁' ，输出：
    [
        {'pinyin': 'sǎ', 'index': 0 },
        {'pinyin': 'bèi', 'index': 1 },
        {'pinyin': 'nìng', 'index': 2 },
    ]
    """
    pinyin_with_index = [
        {"pinyin": x[0], "index": None}
        for x in pinyin(sentence, style, polyphonic_characters)
    ]
    pinyin_with_index_ = iter(pinyin_with_index)
    pinyin = next(pinyin_with_index_)
    for i, char in enumerate(sentence):
        if pinyin["pinyin"] in pinyin(char, style, polyphonic_characters)[0] or pinyin[
            "pinyin"
        ].startswith(char):
            pinyin["index"] = i
            try:
                pinyin = next(pinyin_with_index_)
            except:
                ...
    return pinyin_with_index


def replace_trending_words(sentence):
    """
    从热词词典中查找匹配的热词，替换句子

    句子：       被查找和替换的句子
    """
    all_matches = match_trending_words(sentence)
    for match_items in all_matches:
        word, pinyin_sequence = match_items  # 从字典中找到可以替换的热词和对应的拼音

        sentence_index_list = get_pinyin_index(sentence)
        replace_range = []
        for i, item in enumerate(sentence_index_list):
            for j, sound in enumerate(pinyin_sequence):
                if i + j >= len(sentence_index_list):
                    break
                if sound != sentence_index_list[i + j]["pinyin"]:
                    break
            else:
                replace_range.append(
                    [
                        sentence_index_list[i]["index"],
                        sentence_index_list[i + j]["index"],
                    ]
                )

        for range_ in replace_range:
            sentence = sentence[: range_[0]] + word + sentence[range_[1] + 1 :]

    return sentence


if __name__ == "__main__":
    print(f"\x9b42m-------------开始---------------\x9b0m")

    trending_words_text = """
        撒贝宁
        康辉
        周涛
        乐清
    """

    update_trending_words_dict(trending_words_text)

    t3 = time()
    res = replace_trending_words("在乐清在")
    t4 = time()

    print(f"{res=}    {t4-t3=}")
