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

class NumPyPreprocessor:
    """极致优化版 NumPy 预处理 - 极致对齐 torchaudio 且无需外部矩阵文件"""
    def __init__(self, sr=16000, n_fft=400, n_mels=80, f_min=20, f_max=8000):
        self.sr = sr
        self.n_fft = n_fft
        self.n_mels = n_mels
        
        # 1. 动态生成极致对齐的梅尔矩阵 (复刻 torchaudio 逻辑)
        hz_to_mel = lambda f: 2595.0 * np.log10(1.0 + (f / 700.0))
        mel_to_hz = lambda m: 700.0 * (10.0 ** (m / 2595.0) - 1.0)

        all_freqs = np.linspace(0, sample_rate // 2 if 'sample_rate' in locals() else sr // 2, n_fft // 2 + 1)
        m_pts = np.linspace(hz_to_mel(f_min), hz_to_mel(f_max), n_mels + 2)
        f_pts = mel_to_hz(m_pts)
        f_diff = np.diff(f_pts)
        slopes = f_pts[np.newaxis, :] - all_freqs[:, np.newaxis]
        
        down_slopes = (-1.0 * slopes[:, :-2]) / f_diff[:-1]
        up_slopes = slopes[:, 2:] / f_diff[1:]
        fb = np.maximum(0, np.minimum(down_slopes, up_slopes))
        self.filters = fb.astype(np.float32)
        
        self.hop_length = 160
        # 预计算汉明窗 (纯 NumPy 实现，对齐 torchaudio periodic=True / scipy sym=False)
        self.window = (0.54 - 0.46 * np.cos(2.0 * np.pi * np.arange(self.n_fft) / self.n_fft)).astype(np.float32)
        self.pre_emphasis = 0.97

    def __call__(self, audio):
        # 1. 均值归一化
        audio = audio - np.mean(audio)
        
        # 2. 向量化预加重
        audio_pe = np.empty_like(audio)
        audio_pe[0] = audio[0]
        audio_pe[1:] = audio[1:] - self.pre_emphasis * audio[:-1]
        
        # 3. STFT (使用 np.fft.rfft 获取 20x 加速)
        half_n_fft = self.n_fft // 2
        y = np.pad(audio_pe, (half_n_fft, half_n_fft), mode='constant')
        num_frames = 1 + (len(y) - self.n_fft) // self.hop_length
        frames = np.lib.stride_tricks.as_strided(
            y, 
            shape=(num_frames, self.n_fft), 
            strides=(y.strides[0] * self.hop_length, y.strides[0])
        )
        
        # 加窗并执行 FFT
        win_frames = frames * self.window
        stft_res = np.fft.rfft(win_frames, n=self.n_fft, axis=1)
        magnitudes = np.abs(stft_res)**2 
        
        # 4. Mel 映射与 Log
        mel_spec = np.dot(magnitudes, self.filters) 
        log_mel = np.log(mel_spec + 1e-7)
        
        # 5. LFR 堆叠 (7 帧叠加, 6 帧跳跃)
        T_mel = log_mel.shape[0]
        T_lfr = (T_mel + 5) // 6
        
        left_pad = np.repeat(log_mel[:1, :], 3, axis=0) # m_half=3
        right_pad_len = (T_lfr * 6 + 7) - T_mel
        right_pad = np.repeat(log_mel[-1:, :], right_pad_len, axis=0)
        padded = np.concatenate([left_pad, log_mel, right_pad], axis=0)
        
        lfr_feat = np.empty((T_lfr, 560), dtype=np.float32)
        for i in range(7):
            lfr_feat[:, i*80 : (i+1)*80] = padded[i : i + T_lfr * 6 : 6, :]
            
        return lfr_feat

def load_onnx_models(encoder_path, ctc_path, padding_secs=60, dml_enable=True):
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
    
    # 动态初始化预处理器 (不再依赖外部 .npy)
    encoder_sess.preprocessor = NumPyPreprocessor()

    # 获取输入类型
    enc_in_type = encoder_sess.get_inputs()[0].type
    enc_dtype = np.float16 if 'float16' in enc_in_type else np.float32
    
    ctc_in = ctc_sess.get_inputs()[0]
    ctc_dtype = np.float16 if 'float16' in ctc_in.type else np.float32

    # 温热 (Warmup)
    if padding_secs > 0:
        target_t_lfr = int((padding_secs * 100 + 5) // 6) + 1
        dummy_lfr = np.zeros((1, target_t_lfr, 560), dtype=enc_dtype)
        dummy_mask = np.ones((1, target_t_lfr), dtype=enc_dtype)
        encoder_sess.run(None, {'lfr_feat': dummy_lfr, 'mask': dummy_mask})
        
        # CTC Warmup
        dummy_enc = np.zeros((1, target_t_lfr, 512), dtype=ctc_dtype)
        ctc_sess.run(None, {ctc_in.name: dummy_enc})

    t_cost = time.perf_counter() - t_start
    return encoder_sess, ctc_sess, t_cost

def encode_audio(audio, encoder_sess, padding_secs=60):
    """使用 Clean Encoder 获取嵌入，支持特征级 Padding 以规避 DML 重编译"""
    
    # 1. 外部预处理 (NumPy) - 单独计时
    lfr_feat = encoder_sess.preprocessor(audio)
    
    actual_t_lfr = lfr_feat.shape[0]
    
    # 2. 定长 Padding (针对 LFR 特征级)
    # CPU 模式下可以降低 Padding 长度以节省计算
    if encoder_sess.get_providers()[0] == 'CPUExecutionProvider':
        padding_secs = min(padding_secs, 1.0)
        
    target_t_lfr = int((padding_secs * 100 + 5) // 6) + 1
    
    # 动态类型检测
    enc_in_type = encoder_sess.get_inputs()[0].type
    enc_dtype = np.float16 if 'float16' in enc_in_type else np.float32
    
    if actual_t_lfr < target_t_lfr:
        padded_feat = np.zeros((target_t_lfr, 560), dtype=enc_dtype)
        padded_feat[:actual_t_lfr, :] = lfr_feat.astype(enc_dtype)
        mask = np.zeros(target_t_lfr, dtype=enc_dtype)
        mask[:actual_t_lfr] = 1.0
        lfr_input = padded_feat
        mask_input = mask
    else:
        lfr_input = lfr_feat.astype(enc_dtype)
        mask_input = np.ones(actual_t_lfr, dtype=enc_dtype)

    # 3. 推理 (使用 OrtValue 减少数据拷贝)
    lfr_feed = lfr_input.reshape(1, -1, 560)
    mask_feed = mask_input.reshape(1, -1)
    
    outputs = encoder_sess.run(None, {
        'lfr_feat': lfr_feed,
        'mask': mask_feed
    })
    
    enc_output = outputs[0]  # [1, T_lfr, 512]
    adaptor_raw = outputs[1] # [1, T_adapt, 1024]
    
    # 4. 长度裁切 (计算有效帧数)
    T_mel_valid = (len(audio) // 160) + 1
    T_lfr_valid = (T_mel_valid + 5) // 6
    olens_1 = 1 + (T_lfr_valid - 3 + 2) // 2
    target_len = (1 + (olens_1 - 3 + 2) // 2 - 1) // 2 + 1
    
    audio_embd = adaptor_raw[0, :target_len, :].astype(np.float32)
    
    # 返回值：[1, T, 1024], enc_output, 以及预处理耗时
    return audio_embd, enc_output
