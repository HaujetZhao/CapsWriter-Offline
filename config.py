import os
from collections.abc import Iterable
from pathlib import Path


# 版本信息
__version__ = '2.0'

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# 服务端配置
class ServerConfig:
    addr = '0.0.0.0'
    port = '6014'

    # 语音模型选择：'funasr_nano', 'sensevoice', 'paraformer'
    model_type = 'funasr_nano'

    format_num = True  # 输出时是否将中文数字转为阿拉伯数字
    format_spell = True  # 输出时是否调整中英之间的空格

    enable_tray = True        # 是否启用托盘图标功能

    # 日志配置
    log_level = 'INFO'        # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'


# 客户端配置
class ClientConfig:
    addr = '127.0.0.1'          # Server 地址
    port = '6014'               # Server 端口

    shortcut     = 'caps lock'  # 控制录音的快捷键，默认是 CapsLock
    hold_mode    = True         # 长按模式，按下录音，松开停止，像对讲机一样用。
                                # 改为 False，则关闭长按模式，也就是单击模式
                                #       即：单击录音，再次单击停止
                                #       且：长按会执行原本的单击功能
    suppress     = False        # 是否阻塞按键事件（让其它程序收不到这个按键消息）
    restore_key  = True         # 录音完成，松开按键后，是否自动再按一遍，以恢复 CapsLock 或 Shift 等按键之前的状态
    threshold    = 0.3          # 按下快捷键后，触发语音识别的时间阈值
    paste        = False         # 是否以写入剪切板然后模拟 Ctrl-V 粘贴的方式输出结果
    restore_clip = True         # 模拟粘贴后是否恢复剪贴板

    save_audio = True           # 是否保存录音文件
    audio_name_len = 20         # 将录音识别结果的前多少个字存储到录音文件名中，建议不要超过200

    trash_punc = '，。,.'        # 识别结果要消除的末尾标点

    hot_zh = True               # 是否启用中文热词替换，中文热词存储在 hot_zh.txt 文件里
    多音字 = True                  # True 表示多音字匹配
    声调  = False                 # False 表示忽略声调区别，这样「黄章」就能匹配「慌张」

    hot_en   = True             # 是否启用英文热词替换，英文热词存储在 hot_en.txt 文件里
    hot_rule = True             # 是否启用自定义规则替换，自定义规则存储在 hot_rule.txt 文件里
    hot_kwd  = True             # 是否启用关键词日记功能，自定义关键词存储在 keyword.txt 文件里

    llm_enabled = True           # 是否启用 LLM 润色功能，需要配置 LLM/ 目录下的角色文件
    llm_stop_key = 'esc'        # 中断 LLM 输出的快捷键

    enable_tray = True          # 客户端默认启用托盘图标功能

    # 日志配置
    log_level = 'INFO'          # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    mic_seg_duration = 15           # 麦克风听写时分段长度：15秒
    mic_seg_overlap = 2             # 麦克风听写时分段重叠：2秒

    file_seg_duration = 25           # 转录文件时分段长度
    file_seg_overlap = 2             # 转录文件时分段重叠


class ModelDownloadLinks:
    """模型下载链接配置"""

    # FunASR-nano 模型（推荐，速度快）
    funasr_nano = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-funasr-nano-2025-12-30.tar.bz2"

    # SenseVoice 模型（多语言支持）
    sensevoice = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"

    # Paraformer 模型（暂无官方下载链接）
    paraformer = ""

    # FireRed 模型（大模型，速度慢，不推荐用于实时语音输入）
    firered = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16.tar.bz2"

    # 标点模型
    punct = "https://github.com/k2-fsa/sherpa-onnx/releases/download/punctuation-models/sherpa-onnx-online-punct-en-2024-08-06.tar.bz2"


class ModelPaths:
    # 基础目录
    model_dir = Path() / 'models'

    # Paraformer 模型路径
    paraformer_dir = model_dir / 'Paraformer' / "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    paraformer_model = paraformer_dir / 'model.onnx'
    paraformer_tokens = paraformer_dir / 'tokens.txt'

    # SenseVoice 模型路径
    sensevoice_dir = model_dir / 'SenseVoice-Small' / 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17'
    sensevoice_model = sensevoice_dir / 'model.onnx'
    sensevoice_tokens = sensevoice_dir / 'tokens.txt'

    # FunASR-nano 模型路径
    funasr_nano_dir = model_dir / 'FunASR-nano' / 'sherpa-onnx-funasr-nano-int8-2025-12-30'
    funasr_nano_tokenizer = funasr_nano_dir / 'Qwen3-0.6B'
    funasr_nano_encoder_adaptor = funasr_nano_dir / 'encoder_adaptor.int8.onnx'
    funasr_nano_embedding = funasr_nano_dir / 'embedding.int8.onnx'
    funasr_nano_llm_prefill = funasr_nano_dir / 'llm_prefill.int8.onnx'
    funasr_nano_llm_decode = funasr_nano_dir / 'llm_decode.int8.onnx'

    # 标点模型路径
    punc_model_dir = model_dir / 'Punct-CT-Transformer' / 'sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12' / 'model.onnx'


class ParaformerArgs:
    paraformer = ModelPaths.paraformer_model.as_posix()
    tokens = ModelPaths.paraformer_tokens.as_posix()
    num_threads = 4
    sample_rate = 16000
    feature_dim = 80
    decoding_method = 'greedy_search'
    provider = 'cpu'
    debug = False


class SenseVoiceArgs:
    model = ModelPaths.sensevoice_model.as_posix()
    tokens = ModelPaths.sensevoice_tokens.as_posix()
    use_itn = True
    language = 'zh'
    num_threads = 4
    provider = 'cpu'    # 用 cuda 可以加速，但模型用 CPU 本身也很快，加速没意义
    debug = False


class FunASRNanoArgs:
    encoder_adaptor = ModelPaths.funasr_nano_encoder_adaptor.as_posix()
    llm_prefill = ModelPaths.funasr_nano_llm_prefill.as_posix()
    llm_decode = ModelPaths.funasr_nano_llm_decode.as_posix()
    embedding = ModelPaths.funasr_nano_embedding.as_posix()
    tokenizer = ModelPaths.funasr_nano_tokenizer.as_posix()
    num_threads = 4
    provider = 'cpu'
    debug = False
    system_prompt = "You are a helpful assistant."
    user_prompt = "Transcription:"
    max_new_tokens = 512
    temperature = 0.3
    top_p = 0.8
    seed = 42


