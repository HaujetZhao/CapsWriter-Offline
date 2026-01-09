import re
from string import digits, ascii_letters

en_in_zh = re.compile(r"""(?ix)    # i 表示忽略大小写，x 表示开启注释模式
    ([\u4e00-\u9fa5]|[a-z0-9]+\s)?      # 左侧是中文，或者英文加空格
    ([a-z0-9 ]+)                    # 中间是一个或多个「英文数字加空格」
    ([\u4e00-\u9fa5]|[a-z0-9]+)?       # 右是中文，或者英文加空格
""")

def replacer(original: re.Match):
    left : str = original.group(1)
    center : str = original.group(2)
    right : str = original.group(3)
    # 如果拼写字母中间有空格，就把空格都去掉
    if center:
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', center).strip()
        # 测试地址 https://regex101.com/r/1Vtu7V/1
        # final = re.sub(r'(\b\w) (?!\w{2})', r'\1', original.group(2)).strip()
    
    # 如果英文的左边有汉字或英文，给两组之间加上空格
    if left :
        if left.strip(digits) == left and center.lstrip(digits) == center :  # 左侧结尾不是数字，中间开头不是数字
            final = ' ' + final
        final = left.rstrip() + final
    
    # 如果英文左边的汉字被前一个组消费了，就要手动去看一下前一个字是不是中文
    elif re.match(r'[\u4e00-\u9fa5]', original.string[original.start(2) - 1]): 
        if center.lstrip(digits) == center:     # 确保中间开头不是数字
            final = ' ' + final
        
    # 如果英文的右边有汉字，给中英之间加上空格
    if right:
        if center.rstrip(digits) == center:     # 确保中间结尾不是数字
            final += ' '
        final += right.lstrip()

    return final

def adjust_space(txt):
    return en_in_zh.sub(replacer, txt)

if __name__ == '__main__':
    txt = '''
由个人的需求呢写了这么一个程序，嗯，转字幕视频音频，转字幕不知道取什么名，暂时先叫separwator吧，这是服务端只是客户端，因为服务端需要载入模型，嗯
，把服务端分离出来，可以让它一直运行。这是服务端运行之后，载入模型总共要53秒，语音模型56秒就载入完了。但是这个标点符号模型要花40多秒，载入完之后
，现在我把这音频文件拖动到这个服务客户端上面，然后松手就开始转入了。这是服务端这边总共时长127秒，这样再转入到90秒。好，转入完成了。这个时候在这 
个文件这里就会生成4个文件，一个是march点，t x t这是带有标点符号的。然后再有t x t这是把标点符号的逗号句号和问号全部换成了换行符，就是一行一句。然
后jason在这个jason里边是每一个字它出现的时间，根据每一个字出现的时间和这个一行一段一行一句就可以生成一个s r t，就是生成后的s r t，然后让它硅放一
下数量堆死质量。硅谷王川在网上发了一段文文，他他说所有的我们以为的质量问题大多本质是数量问题，因为 数量不够差几个数量级而已。二、数量就是最重要 
的质量。大部分质量问题在微观上看，就是某个电这个t s d有什么作用呢？就是用于 修改。比如说这个一这个后面我们可以给它加个顿号，然后回车无变声音就出
现了，这里给它换一下。行，有了这个t s d和这个jason在这个youtube里边有个这个脚本，把这个t s t拖动到这上边，然后就会更新一下，生成一个新的s r t， 
这个时候再去播放数量堆死质量 。硅谷王川在网上发了一段文字，他说一看这里这个一这里就有顿号了。这时候一些小量的修小的修改可以在这个t s t里完成。然
后一 更新就生成这个更新后的s r t无边声音就出现了，看这里就换了行了。因为我们有每一个字出现的时间就在这个jason里边就可以，所以就可以进行这样的修 
改。然后它的转录时间r t f0.061，现在是电脑是没有插电，插上电的话是0.03，也就是每100秒钟。嗯 ，每100秒钟只需要3秒钟。嗯，是的，100秒钟，只要3秒钟
就能转录，然后再去试一下。这个这是个两分钟的音频，把它拖动到client上边。在这边我们看一下sir的状态态到133秒，音频30秒60秒、90秒，在这动完成。好，
它完完好，千万不能轻易渡人 的直接嗯，这个速度要比whisper要快多了。
'''
    print(adjust_space(txt))