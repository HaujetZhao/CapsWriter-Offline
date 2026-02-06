import onnxruntime
import time
import os
import numpy as np
from . import logger

"""
ONNX 推理底层工具 - DirectML (DML) 性能优化指南

为什么使用固定 30s 的 padding_secs？

1. 规避重新编译开销：DirectML 会为第一次输入的形状编译 GPU 算子图。根据 ORT 源码，
   Shape 的任何变动都会触发 recompileNeeded，产生约 200ms+ 的编译开销（即“入场券”成本）。

2. 实现全量复用：将短音频补长到 30s，DML 仅需在加载时的“预热”阶段编译一次。后续推理
   将直接命中编译缓存，编码计算仅需约 60ms。对于超过 30S 的音频，200ms 的算子编译开销就可忽略不计了。

3. 配合 input lens 逻辑：通过补零锁定 Shape 解决 recompile 开销，同时利用 ilens 
   提供物理长度信息，在输出端进对结果进行精确裁切，确保 100% 的识别精度。
"""

def load_onnx_models(encoder_path, ctc_path, padding_secs=30, dml_enable=True):
    """步骤 1: 加载 ONNX 音频编码器和 CTC Head 并进行热身"""
    # print("\n[1] 加载 ONNX Models (Encoder + CTC)...")
    
    t_start = time.perf_counter()
    session_opts = onnxruntime.SessionOptions()
    session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
    session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
    session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    
    providers = ['CPUExecutionProvider']
    if dml_enable and 'DmlExecutionProvider' in onnxruntime.get_available_providers():
        providers.insert(0, 'DmlExecutionProvider') 
    logger.info(f"Onnxruntime providers: {providers}")
    
    encoder_sess = onnxruntime.InferenceSession(
        encoder_path, 
        sess_options=session_opts, 
        providers=providers
    )
    
    ctc_sess = onnxruntime.InferenceSession(
        ctc_path, 
        sess_options=session_opts, 
        providers=providers
    )
    
    # Warmup
    if padding_secs > 0:
        # print(f"   [Warmup] Warming up with {warmup_secs}s pseudo-audio...")
        SR = 16000
        warmup_samples = int(SR * padding_secs)  # Ensure int
        
        # Encoder Warmup
        audio_type = encoder_sess.get_inputs()[0].type
        dtype = np.float16 if 'float16' in audio_type else np.float32
        dummy_audio = np.zeros((1, 1, warmup_samples), dtype=dtype)
        dummy_ilens = np.array([warmup_samples], dtype=np.int64)
        
        # New model has ['audio', 'ilens']
        in_names = [x.name for x in encoder_sess.get_inputs()]
        if 'ilens' in in_names:
            encoder_sess.run(None, {in_names[0]: dummy_audio, in_names[1]: dummy_ilens})
        else:
            encoder_sess.run(None, {in_names[0]: dummy_audio})
            
        # CTC Warmup
        ctc_in = ctc_sess.get_inputs()[0]
        ctc_dtype = np.float16 if 'float16' in ctc_in.type else np.float32
        # CTC input shape is [1, T, 512]
        # T_lfr = T_mel // 6, T_mel = audio // 160
        T_warmup = int(warmup_samples // 160 // 6) # Ensure int
        dummy_enc = np.zeros((1, T_warmup, 512), dtype=ctc_dtype)
        ctc_sess.run(None, {ctc_in.name: dummy_enc})

    t_cost = time.perf_counter() - t_start
    return encoder_sess, ctc_sess, t_cost

def encode_audio(audio, encoder_sess, padding_secs=30):
    """使用 ONNX Encoder 获取 LLM 嵌入和 CTC 特征，支持自动 Padding"""
    
    # Check expected input type
    in_names = [x.name for x in encoder_sess.get_inputs()]
    audio_type = encoder_sess.get_inputs()[0].type
    dtype = np.float16 if 'float16' in audio_type else np.float32

    # Padding logic
    actual_samples = len(audio)
    
    # [Optimize] 检测 Provider，如果是 CPU，按最低限度 Padding (因为 CPU 不存在 DML 的重编译开销)
    if encoder_sess.get_providers()[0] == 'CPUExecutionProvider':
        padding_secs = 5
        
    target_samples = int(padding_secs * 16000)
    
    if actual_samples < target_samples:
        # print(f"   [Padding] {actual_samples/16000:.2f}s -> {padding_secs}s")
        padded_audio = np.zeros(target_samples, dtype=audio.dtype)
        padded_audio[:actual_samples] = audio
        audio = padded_audio
    
    audio_input = audio.astype(dtype).reshape(1, 1, -1)
    ilens_input = np.array([actual_samples], dtype=np.int64)
    
    out_names = [x.name for x in encoder_sess.get_outputs()]
    
    # 构造输入 Feed
    if 'ilens' in in_names:
        input_feed = {
            in_names[0]: onnxruntime.OrtValue.ortvalue_from_numpy(audio_input, 'cpu', 0),
            'ilens': onnxruntime.OrtValue.ortvalue_from_numpy(ilens_input, 'cpu', 0)
        }
    else:
        input_feed = {
            in_names[0]: onnxruntime.OrtValue.ortvalue_from_numpy(audio_input, 'cpu', 0)
        }
    
    outputs = encoder_sess.run_with_ort_values(out_names, input_feed)
    
    # Output 0: enc_output [1, T_enc, 512] (For CTC) - 不截断
    enc_output = outputs[0].numpy()
    
    # Output 1: adaptor_output [1, T_llm, 1024] (For LLM) - 需要截断到有效长度
    # 计算有效长度 (llm_target_len)
    T_mel_valid = (actual_samples // 160) + 1
    T_lfr_valid = (T_mel_valid + 5) // 6 # (mel + lfr_n - 1) // lfr_n
    olens_1 = 1 + (T_lfr_valid - 3 + 2) // 2
    target_len = (1 + (olens_1 - 3 + 2) // 2 - 1) // 2 + 1
    
    audio_embd_raw = outputs[1].numpy().squeeze(0)
    # 截断到有效值
    audio_embd = audio_embd_raw[:target_len, :].astype(np.float32)
    
    return audio_embd, enc_output
