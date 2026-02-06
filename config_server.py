import os
from pathlib import Path

# 版本信息
__version__ = '2.4'

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# 服务端配置
class ServerConfig:
    addr = '0.0.0.0'
    port = '6016'

    # 语音模型选择：'fun_asr_nano', 'sensevoice', 'paraformer'
    model_type = 'fun_asr_nano'

    format_num = True       # 输出时是否将中文数字转为阿拉伯数字
    format_spell = True     # 输出时是否调整中英之间的空格

    enable_tray = True        # 是否启用托盘图标功能

    # 日志配置
    log_level = 'INFO'        # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'





class ModelDownloadLinks:
    """模型下载链接配置"""
    # 统一导向 GitHub Release 模型页面
    models_page = "https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models"


class ModelPaths:
    """模型文件路径配置"""

    # 基础目录
    model_dir = Path() / 'models'

    # Paraformer 模型路径
    paraformer_dir = model_dir / 'Paraformer' / "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx"
    paraformer_model = paraformer_dir / 'model.onnx'
    paraformer_tokens = paraformer_dir / 'tokens.txt'

    # 标点模型路径
    punc_model_dir = model_dir / 'Punct-CT-Transformer' / 'sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12' / 'model.onnx'

    # SenseVoice 模型路径，自带标点
    sensevoice_dir = model_dir / 'SenseVoice-Small' / 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17'
    sensevoice_model = sensevoice_dir / 'model.onnx'
    sensevoice_tokens = sensevoice_dir / 'tokens.txt'

    # Fun-ASR-Nano 模型路径，自带标点
    # 默认启用了 DML 对 Encoder 和 CTC 进行加速，显卡用 fp16 模型会更快
    # 但若禁用了 DML，则建议把 Encoder 和 CTC 的 fp16 改为 int8，让可以 CPU 运行更快
    fun_asr_nano_gguf_dir = model_dir / 'Fun-ASR-Nano' / 'Fun-ASR-Nano-GGUF'
    fun_asr_nano_gguf_encoder_adaptor = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-Encoder-Adaptor.fp16.onnx'
    fun_asr_nano_gguf_ctc = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-CTC.fp16.onnx'
    fun_asr_nano_gguf_llm_decode = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-Decoder.q8_0.gguf'
    fun_asr_nano_gguf_token = fun_asr_nano_gguf_dir / 'tokens.txt'
    fun_asr_nano_gguf_hotwords = Path() / 'hot-server.txt'



class ParaformerArgs:
    """Paraformer 模型参数配置"""

    paraformer = ModelPaths.paraformer_model.as_posix()
    tokens = ModelPaths.paraformer_tokens.as_posix()
    num_threads = 4
    sample_rate = 16000
    feature_dim = 80
    decoding_method = 'greedy_search'
    provider = 'cpu'
    debug = False


class SenseVoiceArgs:
    """SenseVoice 模型参数配置"""

    model = ModelPaths.sensevoice_model.as_posix()
    tokens = ModelPaths.sensevoice_tokens.as_posix()
    use_itn = True
    language = 'zh'
    num_threads = 4
    provider = 'cpu'    # 用 cuda 可以加速，但模型用 CPU 本身也很快，加速没意义
    debug = False


class FunASRNanoGGUFArgs:
    """Fun-ASR-Nano-GGUF 模型参数配置"""

    # 模型路径
    encoder_onnx_path = ModelPaths.fun_asr_nano_gguf_encoder_adaptor.as_posix()
    ctc_onnx_path = ModelPaths.fun_asr_nano_gguf_ctc.as_posix()
    decoder_gguf_path = ModelPaths.fun_asr_nano_gguf_llm_decode.as_posix()
    tokens_path = ModelPaths.fun_asr_nano_gguf_token.as_posix()
    hotwords_path = ModelPaths.fun_asr_nano_gguf_hotwords.as_posix()

    # 显卡加速
    dml_enable = True           # 是否启用 DirectML 加速 ONNX 模型
    vulkan_enable = True        # 是否启用 Vulkan 加速 GGUF 模型
    vulkan_force_fp32 = False   # 是否强制 FP32 计算（如果 GPU 是 Intel 集显且出现精度溢出，可设为 True）
    
    # 模型细节
    enable_ctc = True           # 是否启用 CTC 热词检索
    n_predict = 512             # LLM 最大生成 token 数
    n_threads = None            # 线程数，None 表示自动
    similar_threshold = 0.6     # 热词相似度阈值
    max_hotwords = 20           # 每次替换的最大热词数
    verbose = False

