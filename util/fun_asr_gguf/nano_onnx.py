import onnxruntime
import time
import os
import numpy as np

def load_onnx_models(encoder_path, ctc_path):
    """步骤 1: 加载 ONNX 音频编码器和 CTC Head"""
    # print("\n[1] 加载 ONNX Models (Encoder + CTC)...")
    
    t_start = time.perf_counter()
    session_opts = onnxruntime.SessionOptions()
    session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
    session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
    session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    
    encoder_sess = onnxruntime.InferenceSession(
        encoder_path, 
        sess_options=session_opts, 
        providers=['CPUExecutionProvider']
    )
    
    ctc_sess = onnxruntime.InferenceSession(
        ctc_path, 
        sess_options=session_opts, 
        providers=['CPUExecutionProvider']
    )
    
    t_cost = time.perf_counter() - t_start
    
    return encoder_sess, ctc_sess, t_cost

def encode_audio(audio, encoder_sess):
    """使用 ONNX Encoder 获取 LLM 嵌入和 CTC 特征"""
    
    # Reshape: (1, 1, audio_len) and cast to float32
    audio_input = audio.astype(np.float32).reshape(1, 1, -1)
    
    in_names = [x.name for x in encoder_sess.get_inputs()]
    out_names = [x.name for x in encoder_sess.get_outputs()]
    
    # 输入: audio
    # 输出: enc_output, adaptor_output
    input_feed = {
        in_names[0]: onnxruntime.OrtValue.ortvalue_from_numpy(audio_input, 'cpu', 0)
    }
    
    outputs = encoder_sess.run_with_ort_values(out_names, input_feed)
    
    # Output 0: enc_output [1, T_enc, 512] (For CTC)
    enc_output = outputs[0].numpy()
    
    # Output 1: adaptor_output [1, T_llm, 1024] (For LLM)
    audio_embd = outputs[1].numpy().squeeze(0) 
    
    return audio_embd, enc_output
