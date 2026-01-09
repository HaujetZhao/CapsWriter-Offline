from config import ClientConfig as Config

kwd_list = []

def do_updata_kwd(kwd_text: str):
    '''
    把关键词文本中的每一行去除多余空格后添加到列表，
    '''
    kwd_list.clear()
    kwd_list.append('')

    # 如果不启用关键词功能，直接返回
    if not Config.hot_kwd:
        return len(kwd_list)

    # 更新关键词
    for kwd in kwd_text.splitlines():
        kwd = kwd.strip()
        if not kwd or kwd.startswith('#'):
            continue
        kwd_list.append(kwd)

    return len(kwd_list)
