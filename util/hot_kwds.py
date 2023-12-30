

kwd_list = []

def do_updata_kwd(kwd_text: str):
    '''
    把关键词文本中的每一行去除多余空格后添加到列表，
    '''
    kwd_list.clear()
    kwd_list.append('')

    for kwd in kwd_text.splitlines():
        kwd = kwd.strip()
        if not kwd or kwd.startswith('#'):
            continue
        kwd_list.append(kwd)

    return len(kwd_list)
