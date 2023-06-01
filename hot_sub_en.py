import re



'''
热词是每行一个的文本，先更新热词词典，然后再替换句子中的热词。
使用方法示例：


热词文本 = """
    ChatGPT
    Microsoft
"""

更新热词词典(热词文本)

res = 热词替换('the chat gpt is now fully supported by microsoft')

print(res)

'''



__all__ = ['更新热词词典', '热词替换']

热词词典 = {}       


def 更新热词词典(热词文本: str):
    '''
    把热词文本中的每一行去除多余空格后添加到热词词典，
    key 是热词，
    value 是热词的小写
    '''
    global 热词词典; 热词词典.clear()
    for 热词 in 热词文本.splitlines():
        热词 = 热词.strip()
        if not 热词 or 热词.startswith('#'): continue
        热词词典[热词] = re.sub('[^\w]', '', 热词.lower())
    return len(热词词典)


def 匹配热词(句子:str):
    '''
    将全局「热词词典」中的热词按照小写依次与句子匹配，将所有匹配到的热词放到列表
    '''
    global 热词词典

    所有匹配 = []
    小写无空格句子 = 句子.lower().replace(' ', '')
    for 词 in 热词词典:
        if 热词词典[词] in 小写无空格句子:
            所有匹配.append(词)
    
    return 所有匹配

def 热词替换(句子):
    '''
    从热词词典中查找匹配的热词，替换句子

    句子：       被查找和替换的句子
    '''
    所有匹配 = 匹配热词(句子)
    for 匹配项 in 所有匹配:
        正则模式 = re.sub('[^\w]', '', 匹配项)
        正则模式1 = r'(?<=[^a-zA-z])' + re.sub('(.)', r'\1 *?', 正则模式) + r'(?=[^a-zA-z]|\b)'
        正则模式2 = r'(?<=\b)' + re.sub('(.)', r'\1 *?', 正则模式) + r'(?=[^a-zA-z]|\b)'
        句子 = re.sub(正则模式1, 匹配项, 句子, flags=re.I)
        句子 = re.sub(正则模式2, 匹配项, 句子, flags=re.I)
    return 句子

if __name__ == '__main__':
    print(f'\x9b42m-------------开始---------------\x9b0m')

    热词文本 = '''
        ChatGPT
        Microsoft
        CD-ROM
        iPhone4S
        7-Zip
        AI
        CapsWriter
        GB
        IP
    '''

    更新热词词典(热词文本)

    res = 热词替换('7 zip测试')


    print(f'{res}')

