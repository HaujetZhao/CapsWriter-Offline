
kwd_list = []

def do_updata_kwd(kwd_text: str):
    '''
    把关键词文本中的每一行去除多余空格后添加到列表，
    '''
    kwd_list.clear()
    kwd_list.append('')

    # 如果不启用关键词功能，直接返回
    # Caller should check config
    # if not Config.hot_kwd:
    #    return len(kwd_list)



    # 更新关键词
    for kwd in kwd_text.splitlines():
        kwd = kwd.strip()
        if not kwd or kwd.startswith('#'):
            continue
        kwd_list.append(kwd)

    return len(kwd_list)


if __name__ == '__main__':
    print('-------------开始---------------')
    
    # 模拟 Config
    import config
    class MockConfig:
        hot_kwd = True
    config.ClientConfig = MockConfig
    
    kwd_text = '''
        重要
        健康
        学习
    '''
    
    num = do_updata_kwd(kwd_text)
    print(f"更新了 {num} 个关键词")
    print(f"列表: {kwd_list}")

