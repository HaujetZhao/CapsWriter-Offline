from pypinyin import pinyin
from time import time

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

res = 热词替换('我有个同学叫李佳一')

print(res)

'''




__all__ = ['更新热词词典', '热词替换', '多音字', '声调']


# ================全局配置=======================


热词词典 = {}
多音字 = True
声调 = False     # 是否要求匹配声调


# ===========================================


风格 = 1 if 声调 else 0     # 依据是否需要声调，设置拼音风格

def 更新热词词典(热词文本: str):
    '''
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
    '''
    global 热词词典; 热词词典.clear()
    for 热词 in 热词文本.splitlines():
        热词 = 热词.strip()                             # 给热词去掉多余的空格
        if not 热词 or 热词.startswith('#'): continue   # 过滤掉注释
        热词拼音 = pinyin(热词, 风格, 多音字)     # 得到拼音

        if len(热词拼音) != len(热词): 
            print(f'\x9b31m    热词「{热词}」得到的拼音数量与字数不符，抛弃\x9b0m')
            continue

        拼音列表 = [[], ]
        for 多音 in 热词拼音: 
            音数 = len(多音)
            if 音数 > 1:
                原始列表, 拼音列表 = 拼音列表, []
                for 音 in 多音:
                    拼音列表.extend([x.copy() + [音] for x in 原始列表])
            else:
                for x in 拼音列表: x.append(多音[0])
        
        热词词典[热词] = 拼音列表
    return len(热词词典)


def 匹配热词(句子:str):
    '''
    将全局「热词词典」中的热词按照拼音依次与句子匹配，将所有匹配到的「热词、拼音」以元组放到列表
    将列表返回
    '''
    global 热词词典

    所有匹配 = []
    句子拼音 = ''.join([x[0] for x in pinyin(句子, 风格, 多音字)])  # 字符串形式的句子拼音
    for 词 in 热词词典.keys():
        for 拼音序列 in 热词词典[词]:
            if ''.join(拼音序列) in 句子拼音: 
                所有匹配.append((词, 拼音序列))
            else: 
                continue
    return 所有匹配


def 获取拼音索引(句子: str):
    '''
    输入句子字符串，获取一个列表，列表内是字典，字典包含了拼音和索引

    例如，输入 '撒贝宁' ，输出：
    [
        {'pinyin': 'sǎ', 'index': 0 }, 
        {'pinyin': 'bèi', 'index': 1 }, 
        {'pinyin': 'nìng', 'index': 2 }, 
    ]
    '''
    拼音带索引 = [{'pinyin': x[0], 'index': None} for x in pinyin(句子, 风格, 多音字)]
    拼音带索引_ = iter(拼音带索引)
    拼音 = next(拼音带索引_)
    for i, 字 in enumerate(句子):
        if 拼音['pinyin'] in pinyin(字, 风格, 多音字)[0] or 拼音['pinyin'].startswith(字):
            拼音['index'] = i
            try: 拼音 = next(拼音带索引_)
            except: ...
    return 拼音带索引


def 热词替换(句子):
    '''
    从热词词典中查找匹配的热词，替换句子

    句子：       被查找和替换的句子
    '''
    所有匹配 = 匹配热词(句子)
    for 匹配项 in 所有匹配:
        热词, 拼音序列 = 匹配项  # 从字典中找到可以替换的热词和对应的拼音
        
        句子索引表 = 获取拼音索引(句子)
        替换区间 = []
        for i, item in enumerate(句子索引表):
            for j, 音 in enumerate(拼音序列):
                if i+j >= len(句子索引表): break
                if 音 != 句子索引表[i+j]['pinyin']: break
            else:
                替换区间.append([句子索引表[i]['index'], 句子索引表[i+j]['index']])

        for 区间 in 替换区间:
            句子 = 句子[:区间[0]] + 热词 + 句子[区间[1]+1:]

    return 句子


if __name__ == '__main__':
    print(f'\x9b42m-------------开始---------------\x9b0m')

    热词文本 = '''
        撒贝宁
        康辉
        周涛
        乐清
    '''

    更新热词词典(热词文本)

    t3 = time()
    res = 热词替换('在乐清在')
    t4 = time()

    print(f'{res=}    {t4-t3=}')
