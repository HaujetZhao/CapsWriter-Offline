# coding: utf-8
"""
这个文件仅仅是为了 PyInstaller 打包用
"""

import sys
import typer
from core_client import init_mic, init_file
import threading
import multiprocessing
import os
import PySimpleGUI as sg
import threading
from util.server_client_state  import uic
from util.server_client_state import client_is_running, server_is_running
from util.client_cosmic import Cosmic, console



# 获取程序的根目录，用于打开文件和加载模型
BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)


def open_file(file):
    # 获取用户的主目录
    home_dir = os.path.expanduser('~')
    # 在用户的主目录中查找文件
    file_path = os.path.join(home_dir, file)
    extension = os.path.splitext(file_path)[1]
    if extension == '.txt':
        os.system(f"notepad {file_path}")
    elif extension == '.json':
        os.system(f"notepad {file_path}")
    elif extension == '.srt':
        os.system(f"start {file_path}")  # 使用默认的程序打开 .srt 文件
    elif extension == '.py':
        os.system(f"notepad {file_path}")  # 使用 Notepad 打开 .py 文件
    else:
        os.system(f"start {file_path}")  # 对于其他类型的文件，使用默认的程序打开


# 创建一个共享变量，用于控制客户端程序是否运行
client_is_running = multiprocessing.Value('b', True)
# 创建一个共享变量，用于控制客户端程序是否运行
gui_is_running = multiprocessing.Value('b', True)



# 创建GUI窗口
def create_gui(gui_is_running):
    # 创建GUI线程
    gui_thread = threading.Thread(target=gui_program, args=(gui_is_running,))
    gui_thread.start()
    return gui_thread


# 客户端程序
def client_program(client_is_running):
    #print(client_is_running.value)
    while client_is_running.value:
        init_mic(client_is_running)# 启动客户端程序
        # 如果客户端程序停止运行，就退出循环
        if not client_is_running.value:
            break
        # 如果客户端程序在运行，就继续运行
        else:
            continue
        

# 创建GUI窗口
def gui_program(gui_is_running):
    
    
    languages = ['英文', '中文', '法文', '德文', '日文', '韩文','藏文']  # 添加你需要的语言
    
    # 创建按钮
    layout = [
        #[sg.Text("连接中", key="-CONN_STATUS-", size=(6, 1),)],
        [
            sg.Column(
                [
                    [
                        sg.Radio('转文字', "RADIO1", default=True, key='-TOTEXT-', enable_events=True),
                        sg.Radio('翻译', "RADIO1", default=False, key='-TRANSLATE-', enable_events=True),
                        sg.Radio('助手', "RADIO1", default=False, key='-ASSISTANT-', enable_events=True),
                    ]
                ],
                justification='center'
            ),
        ],
        
                [
            sg.Column(
                [
                    [
                        sg.Combo(languages, default_value=languages[0], key='-LANGUAGE-', enable_events=True, size=(6, 1), readonly=True, disabled=True),  # 添加下拉框
                        sg.Checkbox('保留原文', default=True, key='-KEEP_ORIGINAL-',enable_events=True,disabled=True)  # 是否保留原文
                    ]
                ],
                justification='center'
            ),
        ],
        
        [
            sg.Column(
                [
                    [
                        sg.Button("中\n文\n热\n词", key="-CN_HOT_WORDS-", size=(3, 6), button_color=("black", "white")),
                        sg.Button("英\n文\n热\n词", key="-EN_HOT_WORDS-", size=(3, 6), button_color=("black", "white")),
                        sg.Button("关\n 键 \n字", key="-KEYWORDS-", size=(3, 6), button_color=("black", "white")),
                        sg.Button("定\n义\n规\n则", key="-DEFRULE-", size=(3, 6), button_color=("black", "white")),
                        sg.Button("配\n置\n文\n件", key="-CONFIG-", size=(3, 6), button_color=("black", "white"))
                    ]
                ],
                justification='center'
            )
        ]
    ]
    
    # 创建窗口
    # 获取屏幕大小
    screen_width, screen_height = sg.Window.get_screen_size()

    # 计算窗口的初始位置
    x = screen_width - 280 - 30  # 窗口宽度
    y = screen_height - 150 - 90  # 窗口高度，减去任务栏的高度

    window = sg.Window("客户端配置", layout, finalize=True, alpha_channel=0.6,  size=(300, 170), location=(x, y), icon='.\\AiMa.ico')

    # 事件循环
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            client_is_running.value = False
            break
        elif event == '-KEEP_ORIGINAL-':  # 当 "保留原文" 选项被切换时
            uic.keep_original = values['-KEEP_ORIGINAL-']
            if uic.keep_original:
                console.print('保留原文开启')
            else:
                console.print('保留原文关闭')

        elif event in ("-TOTEXT-", "-ASSISTANT-", "-TRANSLATE-"):
            uic.totext_is_running = values["-TOTEXT-"]
            uic.assistant_is_running = values["-ASSISTANT-"]
            uic.translate_is_running = values["-TRANSLATE-"]

            if uic.totext_is_running:
                console.print('转文字已经启动')
                uic.assistant_is_running = False
                uic.translate_is_running = False
                window['-KEEP_ORIGINAL-'].update(disabled=True)  # 禁用 "保留原文" 复选框
                window['-LANGUAGE-'].update(disabled=True)  # 禁用 "语言选择" 复选框
            elif uic.assistant_is_running:
                console.print('助手已经启动')
                uic.totext_is_running = False
                uic.translate_is_running = False
                window['-KEEP_ORIGINAL-'].update(disabled=True)  # 禁用 "保留原文" 复选框
                window['-LANGUAGE-'].update(disabled=True)  # 禁用 "语言选择" 复选框
            elif uic.translate_is_running:
                console.print('翻译已经启动')
                uic.totext_is_running = False
                uic.assistant_is_running = False
                window['-KEEP_ORIGINAL-'].update(disabled=False)  # 启用 "保留原文" 复选框
                window['-LANGUAGE-'].update(disabled=False)  # 启用 "语言选择" 复选框
                
        elif event == "-LANGUAGE-":
            uic.target_language = values[event]
            console.print(f"目标语言:{uic.target_language}")
        elif event == "-CN_HOT_WORDS-":
            open_file(os.path.join(BASE_DIR, "hot-zh.txt"))
        elif event == "-EN_HOT_WORDS-":
            open_file(os.path.join(BASE_DIR, "hot-en.txt"))
        elif event == "-KEYWORDS-":
            open_file(os.path.join(BASE_DIR, "keywords.txt"))
        elif event == "-DEFRULE-":
            open_file(os.path.join(BASE_DIR, "hot-rule.txt"))
        elif event == "-CONFIG-":
            open_file(os.path.join(BASE_DIR, "config.py"))
        elif event == sg.WINDOW_CLOSED  or event == "-EXIT-":
            client_is_running.value = False
            gui_is_running.value = False
            print(gui_is_running.value)
            print(client_is_running.value)
            break
        
    window.close()
        
if __name__ == "__main__":
    # 如果参数传入文件，那就转录文件
    # 如果没有多余参数，就从麦克风输入
    if sys.argv[1:]:
        typer.run(init_file)
    else:
        # 在主程序中启动GUI程序
        create_gui(gui_is_running)
        # 在主程序中启动客户端程序
        client_program(client_is_running)




    
    