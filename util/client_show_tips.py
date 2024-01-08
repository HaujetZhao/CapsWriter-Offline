import os

from util.client_cosmic import console
from config import ClientConfig as Config
from rich.markdown import Markdown


def show_mic_tips():
    console.rule('[bold #d55252]CapsWriter Offline Client')
    # console.print(f'\n项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    markdown = (f'''

项目地址：https://github.com/HaujetZhao/CapsWriter-Offline

这是 CapsWriter-Offline，一个好用的离线语音输入工具。

使用步骤：

1. 运行 Server 端，它会载入语音和标点模型（共占用约 2GB 的内存）
2. 运行 Client 端，它会打开系统默认麦克风（Ctrl+C 可重载麦克风）
3. 按住 `{Config.shortcut}` 键，录音开始，松开 `{Config.shortcut}` 键，录音结束，识别结果立刻被输入
4. 将音视频文件拖动到 Client 端打开，可以转录生成字幕


特性：

1. 完全离线、无限时长、低延迟、高准确率、中英混输、自动阿拉伯数字、自动调整中英间隔
2. 热词功能：可以在 `hot-en.txt hot-zh.txt hot-rule.txt` 中添加三种热词，客户端动态载入
3. 日记功能：默认每次录音识别后，识别结果记录在 `年份/月份/日期.md` ，录音文件保存在 `年份/月份/assets` 
4. 关键词日记：识别结果若以关键词开头，会被记录在 `年份/月份/关键词-日期.md`，关键词在 `keywords.txt` 中定义
5. 转录功能：将音视频文件拖动到客户端打开，即可转录生成 srt 字幕
6. 服务端、客户端分离，可以服务多台客户端
7. 编辑 `config.py` ，可以配置服务端地址、快捷键、录音开关……


注意事项：

1. 当用户安装了 `FFmpeg` 时，会以 `mp3` 格式保存录音；当用户没有装 `FFmpeg` 时，会以 `wav` 格式保存录音
2. 音视频文件转录功能依赖于 `FFmpeg`
3. 默认的快捷键是 {Config.shortcut}，你可以打开 `core_client.py` 进行修改
4. MacOS 无法监测到 `caps lock` 按键，可改为 `right shift` 按键
    ''')
    console.print(Markdown(markdown), highlight=True)
    console.rule()
    console.print(f'\n当前基文件夹：[cyan underline]{os.getcwd()}')
    console.print(f'\n服务端地址： [cyan underline]{Config.addr}:{Config.port}')
    console.print(f'\n当前所用快捷键：[green4]{Config.shortcut}')

    console.line()


def show_file_tips():
    markdown = f'\n项目地址：https://github.com/HaujetZhao/CapsWriter-Offline'
    console.print(Markdown(markdown), height=True)
    console.print(f'当前基文件夹：[cyan underline]{os.getcwd()}')
    console.print(f'服务端地址： [cyan underline]{Config.addr}:{Config.port}')
