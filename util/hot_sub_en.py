import re

'''
Trending words are one per line text, first update the trending words dictionary, and then replace the trending words in the sentence.
Usage example:


trending_words_text = """
    ChatGPT
    Microsoft
"""

update_trending_words_dict(trending_words_text)

res = replace_trending_words('the chat gpt is now fully supported by microsoft')

print(res)

'''


__all__ = ["update_trending_words_dict", "replace_trending_words"]

trending_words_dict = {}


def update_trending_words_dict(trending_words_text: str):
    """
    Remove extra spaces from each line in the trending words text and add it to the trending words dictionary,
    key is the trending word,
    value is the lowercase of the trending word
    """
    global trending_words_dict
    trending_words_dict.clear()
    for word in trending_words_text.splitlines():
        word = word.strip()
        if not word or word.startswith("#"):
            continue
        trending_words_dict[word] = re.sub("[^\w]", "", word.lower())
    return len(trending_words_dict)


def match_trending_words(sentence: str):
    """
    Match the trending words in the global "trending_words_dict" with the sentence in lowercase, and put all matched trending words into a list
    """
    global trending_words_dict

    all_matches = []
    lowercase_no_space_sentence = sentence.lower().replace(" ", "")
    for word in trending_words_dict:
        if trending_words_dict[word] in lowercase_no_space_sentence:
            all_matches.append(word)

    return all_matches


def replace_trending_words(sentence):
    """
    Find and replace trending words from the trending words dictionary in the sentence

    sentence:       The sentence to be searched and replaced
    """
    all_matches = match_trending_words(sentence)
    for match_item in all_matches:
        regex_pattern = re.sub("[^\w]", "", match_item)
        regex_pattern1 = (
            r"(?<=[^a-zA-z])"
            + re.sub("(.)", r"\1 *?", regex_pattern)
            + r"(?=[^a-zA-z]|\b)"
        )
        regex_pattern2 = (
            r"(?<=\b)" + re.sub("(.)", r"\1 *?", regex_pattern) + r"(?=[^a-zA-z]|\b)"
        )
        sentence = re.sub(regex_pattern1, match_item, sentence, flags=re.I)
        sentence = re.sub(regex_pattern2, match_item, sentence, flags=re.I)
    return sentence


if __name__ == "__main__":
    print(f"\x9b42m-------------开始---------------\x9b0m")

    trending_words_text = """
        ChatGPT
        Microsoft
        CD-ROM
        iPhone4S
        7-Zip
        AI
        CapsWriter
        GB
        IP
    """

    update_trending_words_dict(trending_words_text)

    res = replace_trending_words("7 zip测试")

    print(f"{res}")
