# coding: utf-8
"""
模型配置模块

包含所有语音识别模型的下载链接、路径配置和参数配置。
"""

from pathlib import Path



class ModelDownloadLinks:
    """模型下载链接配置"""

    # FunASR-nano 模型（推荐，速度快）
    funasr_nano = "https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/sherpa-onnx-funasr-nano-int8-2025-12-30.zip"

    # SenseVoice 模型（多语言支持）
    sensevoice = "https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.zip"

    # Paraformer 模型（HuggingFace下载链接）
    paraformer = "https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx.zip"

    # FireRed 模型（大模型，速度慢，不推荐用于实时语音输入，未实施）
    firered = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16.tar.bz2"

    # 标点模型
    punct = "https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12.zip"


class ModelPaths:
    """模型文件路径配置"""

    # 基础目录
    model_dir = Path() / 'models'

    # Paraformer 模型路径
    paraformer_dir = model_dir / 'Paraformer' / "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx"
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

    fun_asr_nano_gguf_dir = model_dir / 'FunASR-Nano' / 'Fun-ASR-Nano-GGUF'
    fun_asr_nano_gguf_encoder_adaptor = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-Encoder-Adaptor.fp32.onnx'
    fun_asr_nano_gguf_ctc = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-CTC.int8.onnx'
    fun_asr_nano_gguf_llm_decode = fun_asr_nano_gguf_dir / 'Fun-ASR-Nano-Decoder.q8_0.gguf'
    fun_asr_nano_gguf_token = fun_asr_nano_gguf_dir / 'tokens.txt'
    fun_asr_nano_gguf_hotwords = Path() / 'hot.txt'

    # 标点模型路径
    punc_model_dir = model_dir / 'Punct-CT-Transformer' / 'sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12' / 'model.onnx'


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


class FunASRNanoArgs:
    """Fun-ASR-nano 模型参数配置"""

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

class FunASRNanoGGUFArgs:
    """Fun-ASR-nano 模型参数配置"""

    encoder_onnx_path=ModelPaths.fun_asr_nano_gguf_encoder_adaptor.as_posix()
    ctc_onnx_path=ModelPaths.fun_asr_nano_gguf_ctc.as_posix()
    decoder_gguf_path=ModelPaths.fun_asr_nano_gguf_llm_decode.as_posix()
    tokens_path=ModelPaths.fun_asr_nano_gguf_token.as_posix()
    hotwords_path=ModelPaths.fun_asr_nano_gguf_hotwords.as_posix()
    enable_ctc=True
    verbose=True
