import os
from collections.abc import Iterable
from pathlib import Path

# 版本信息
__version__ = '2.2'

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# 服务端配置
class ServerConfig:
    addr = '0.0.0.0'
    port = '6016'

    # 语音模型选择：'funasr_nano', 'sensevoice', 'paraformer'
    model_type = 'funasr_nano'

    format_num = True       # 输出时是否将中文数字转为阿拉伯数字
    format_spell = True     # 输出时是否调整中英之间的空格

    enable_tray = True        # 是否启用托盘图标功能

    # 日志配置
    log_level = 'INFO'        # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'


# 客户端配置
class ClientConfig:
    addr = '127.0.0.1'          # Server 地址
    port = '6016'               # Server 端口

    # 快捷键配置列表
    # 支持多个快捷键同时工作，每个快捷键配置说明：
    # - key: 快捷键名称（pynput 格式，如 'caps_lock', 'f12', 'space'）
    # - type: 'keyboard' 或 'mouse'
    # - suppress: 是否阻塞按键事件
    # - restore: 录音完成后是否恢复按键状态（仅对 CapsLock 等切换键有效）
    # - hold_mode: True=长按模式，False=单击模式
    # - enabled: 是否启用
    shortcuts = [
        {
            'key': 'caps_lock',
            'type': 'keyboard',
            'suppress': False,
            'restore': True,
            'hold_mode': True,
            'enabled': True
        },
        # 可添加更多快捷键，例如：
        # {
        #     'key': 'f12',
        #     'type': 'keyboard',
        #     'suppress': False,
        #     'restore': False,
        #     'hold_mode': True,
        #     'enabled': False
        # },
        {
            'key': 'x2',
            'type': 'mouse',
            'suppress': True,
            'restore': False,
            'hold_mode': True,
            'enabled': True
        },
    ]

    threshold    = 0.3          # 快捷键触发阈值（秒）

    paste        = False        # 是否以写入剪切板然后模拟 Ctrl-V 粘贴的方式输出结果
    restore_clip = True         # 模拟粘贴后是否恢复剪贴板

    save_audio = True           # 是否保存录音文件
    audio_name_len = 20         # 将录音识别结果的前多少个字存储到录音文件名中，建议不要超过200

    trash_punc = '，。,.'       # 识别结果要消除的末尾标点

    traditional_convert = False     # 是否将识别结果转换为繁体中文
    traditional_locale = 'zh-hant'  # 繁体地区：'zh-hant'（标准繁体）, 'zh-tw'（台湾繁体）, 'zh-hk'（香港繁体）

    hot = True                  # 是否启用热词替换（统一 RAG 匹配）
    hot_thresh = 0.85           # RAG 替换热词阈值（高阈值，用于实际替换）
    hot_similar = 0.6           # RAG 相似热词阈值（低阈值，用于 LLM 上下文）
    hot_rectify = 0.6           # 纠错历史 RAG 匹配阈值（低阈值，用于 LLM 上下文）
    hot_rule = True             # 是否启用自定义规则替换（基于正则表达式）

    llm_enabled = True          # 是否启用 LLM 润色功能，需要配置 LLM/ 目录下的角色文件
    llm_stop_key = 'esc'        # 中断 LLM 输出的快捷键

    enable_tray = True          # 客户端默认启用托盘图标功能

    # 日志配置
    log_level = 'INFO'          # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    mic_seg_duration = 25       # 麦克风听写时分段长度：15秒
    mic_seg_overlap = 2         # 麦克风听写时分段重叠：2秒

    file_seg_duration = 25      # 转录文件时分段长度
    file_seg_overlap = 2        # 转录文件时分段重叠

    udp_broadcast = True                # 是否启用 UDP 广播输出结果
    udp_broadcast_targets = [           # UDP 广播目标地址列表，格式: (地址, 端口)
        ('127.255.255.255', 6017),      # 本地回环广播
        # ('192.168.1.255', 6017),      # 局域网广播（示例，按需启用）
    ]

    udp_control = False             # 是否启用 UDP 控制录音（外部程序发送 START/STOP 命令）
    udp_control_addr = '127.0.0.1'  # UDP 控制监听地址（'0.0.0.0' 允许外部访问）
    udp_control_port = 6018         # UDP 控制监听端口

