from dataclasses import dataclass
from pathlib import Path


# 服务端配置
@dataclass(frozen=True)
class ServerConfig:
    addr = "0.0.0.0"
    port = 6016
    format_num = True  # 输出时是否将中文数字转为阿拉伯数字
    format_punc = True  # 输出时是否启用标点符号引擎
    format_spell = True  # 输出时是否调整中英之间的空格


# 客户端配置
@dataclass(frozen=True)
class ClientConfig:
    addr = "127.0.0.1"  # Server 地址
    port = 6016  # Server 端口

    shortcut = "caps lock"  # 控制录音的快捷键，默认是 CapsLock
    hold_mode = True  # 长按模式，按下录音，松开停止，像对讲机一样用。
    # 改为 False，则关闭长按模式，也就是单击模式
    #       即：单击录音，再次单击停止
    #       且：长按会执行原本的单击功能
    suppress = False  # 是否阻塞按键事件（让其它程序收不到这个按键消息）
    restore_key = True  # 录音完成，松开按键后，是否自动再按一遍，以恢复 CapsLock 或 Shift 等按键之前的状态
    threshold = 0.3  # 按下快捷键后，触发语音识别的时间阈值
    paste = True  # 是否以写入剪切板然后模拟 Ctrl-V 粘贴的方式输出结果
    restore_clip = True  # 模拟粘贴后是否恢复剪贴板

    save_audio = True  # 是否保存录音文件
    audio_name_len = (
        20  # 将录音识别结果的前多少个字存储到录音文件名中，建议不要超过200
    )

    trash_punc = "，。,."  # 识别结果要消除的末尾标点

    hot_zh = True  # 是否启用中文热词替换，中文热词存储在 hot_zh.txt 文件里
    polyphonic_characters = True  # True 表示多音字匹配
    tones = False  # False 表示忽略声调区别，这样「黄章」就能匹配「慌张」

    hot_en = True  # 是否启用英文热词替换，英文热词存储在 hot_en.txt 文件里
    hot_rule = (
        True  # 是否启用自定义规则替换，自定义规则存储在 hot_rule.txt 文件里
    )
    hot_kwd = (
        True  # 是否启用关键词日记功能，自定义关键词存储在 keyword.txt 文件里
    )

    mic_seg_duration = 15  # 麦克风听写时分段长度：15秒
    mic_seg_overlap = 2  # 麦克风听写时分段重叠：2秒

    file_seg_duration = 25  # 转录文件时分段长度
    file_seg_overlap = 2  # 转录文件时分段重叠


@dataclass(frozen=True)
class ModelPaths:
    model_dir = Path() / "models"
    paraformer_path = (
        Path() / "models" / "paraformer-offline-zh" / "model.int8.onnx"
    )
    tokens_path = Path() / "models" / "paraformer-offline-zh" / "tokens.txt"
    punc_model_dir = Path() / "models" / "punc_ct-transformer_cn-en"


@dataclass(frozen=True)
class ParaformerArgs:
    paraformer = f"{ModelPaths.paraformer_path}"
    tokens = f"{ModelPaths.tokens_path}"
    num_threads = 6
    sample_rate = 16000
    feature_dim = 80
    decoding_method = "greedy_search"
    debug = False
