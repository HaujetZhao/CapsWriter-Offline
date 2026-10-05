"""Suppress complete microphone utterances consisting solely of fillers."""
import re
import unicodedata

CHINESE_FILLERS = frozenset('嗯呃额啊阿哦噢喔唔哎欸诶咦唉哼哈嘿嗨呀哟呦啦呢吧嘛呵啧嘘嗷呸吁哇嚯咳')
ENGLISH_FILLER = re.compile(r'(?:u+m+|u+h+|a+h+|o+h+|h+m+|m+h+m*|m+|e+r+m*|e+h+|h+u+h+|yeah|yea|yep|wow|hey|hi|aha|(?:ha)+|he+h+)')


def is_filler_only(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in normalized)
    parts = re.findall(r'[a-z]+|[\u4e00-\u9fff]+|[^\s]', normalized)
    if not parts:
        return False
    return all(ENGLISH_FILLER.fullmatch(part) or all(c in CHINESE_FILLERS for c in part) for part in parts)


def suppress_filler_only(result):
    if result.type != 'mic':
        return False
    texts = [text for text in (result.text, result.text_accu) if text.strip()]
    if not texts or not all(is_filler_only(text) for text in texts):
        return False
    result.text = result.text_accu = ''
    result.tokens = []
    result.timestamps = []
    return True
