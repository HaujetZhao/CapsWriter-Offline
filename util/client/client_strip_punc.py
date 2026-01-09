from config import ClientConfig as Config


def strip_punc(text: str) -> str:
    return text.strip(Config.trash_punc)
