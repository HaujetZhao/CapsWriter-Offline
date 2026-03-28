import onnxruntime
import time
import os
import numpy as np
from . import logger

class FunASRMelExtractor:
    """FunASR 专用 Mel 特征提取器 - 极致对齐 torchaudio"""
    def __init__(self, sr=16000, n_fft=400, n_mels=80, f_min=20, f_max=8000):
        self.sr = sr
        self.n_fft = n_fft
        self.n_mels = n_mels
        
        # 1. 动态生成极致对齐的梅尔矩阵 (复刻 torchaudio 逻辑)
        hz_to_mel = lambda f: 2595.0 * np.log10(1.0 + (f / 700.0))
        mel_to_hz = lambda m: 700.0 * (10.0 ** (m / 2595.0) - 1.0)

        all_freqs = np.linspace(0, sr // 2, n_fft // 2 + 1)
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

    def extract(self, audio: np.ndarray) -> np.ndarray:
        # 1. 均值归一化
        audio = audio - np.mean(audio)
        
        # 2. 向量化预加重
        audio_pe = np.empty_like(audio)
        audio_pe[0] = audio[0]
        audio_pe[1:] = audio[1:] - self.pre_emphasis * audio[:-1]
        
        # 3. STFT (使用 np.fft.rfft)
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

class AudioEncoder:
    """FunASR 音频编码器 (基于 ONNX Runtime)"""
    def __init__(self, model_path: str, dml_enable: bool = True, pad_to: int = 30):
        self.model_path = model_path
        self.dml_enable = dml_enable
        self.pad_to = pad_to
        
        self.sess = None
        self.preprocessor = FunASRMelExtractor()
        self.input_dtype = np.float32
        self._initialize_session()

    def _initialize_session(self):
        session_opts = onnxruntime.SessionOptions()
        session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        providers = ['CPUExecutionProvider']
        if self.dml_enable and 'DmlExecutionProvider' in onnxruntime.get_available_providers():
            providers.insert(0, 'DmlExecutionProvider') 
        
        logger.info(f"[Encoder] 加载模型: {os.path.basename(self.model_path)} (Providers: {providers})")
        
        self.sess = onnxruntime.InferenceSession(
            self.model_path, 
            sess_options=session_opts, 
            providers=providers
        )
        
        # 检测模型输入精度
        in_type = self.sess.get_inputs()[0].type
        self.input_dtype = np.float16 if 'float16' in in_type else np.float32
        
        # 自动热身
        self.warmup()

    def warmup(self):
        """执行热身，确保 DML 算子已编译"""
        if self.pad_to <= 0:
            return
            
        target_t_lfr = int((self.pad_to * 100 + 5) // 6) + 1
        dummy_lfr = np.zeros((1, target_t_lfr, 560), dtype=self.input_dtype)
        dummy_mask = np.ones((1, target_t_lfr), dtype=self.input_dtype)
        
        logger.info(f"[Encoder] 正在预热 (固定形状: {self.pad_to}s)...")
        self.sess.run(None, {'lfr_feat': dummy_lfr, 'mask': dummy_mask})

    def encode(self, audio: np.ndarray) -> tuple:
        """执行编码，返回 (audio_embeddings, encoder_output)"""
        # 1. 预处理
        lfr_feat = self.preprocessor.extract(audio)
        actual_t_lfr = lfr_feat.shape[0]
        
        # 2. 确定 Padding 长度
        # CPU 模式下无需长 Padding
        padding_secs = self.pad_to
        if self.sess.get_providers()[0] == 'CPUExecutionProvider':
            padding_secs = min(padding_secs, 1.0)
            
        target_t_lfr = int((padding_secs * 100 + 5) // 6) + 1
        
        # 3. 执行 Padding 以规避 DML 重编译
        if actual_t_lfr < target_t_lfr:
            padded_feat = np.zeros((target_t_lfr, 560), dtype=self.input_dtype)
            padded_feat[:actual_t_lfr, :] = lfr_feat.astype(self.input_dtype)
            mask = np.zeros(target_t_lfr, dtype=self.input_dtype)
            mask[:actual_t_lfr] = 1.0
            lfr_input = padded_feat
            mask_input = mask
        else:
            lfr_input = lfr_feat.astype(self.input_dtype)
            mask_input = np.ones(actual_t_lfr, dtype=self.input_dtype)

        # 4. 推理
        lfr_feed = lfr_input.reshape(1, -1, 560)
        mask_feed = mask_input.reshape(1, -1)
        
        outputs = self.sess.run(None, {
            'lfr_feat': lfr_feed,
            'mask': mask_feed
        })
        
        enc_output = outputs[0]  # [1, T_lfr, 512]
        adaptor_raw = outputs[1] # [1, T_adapt, 1024]
        
        # 5. 后处理：长度裁切 (计算有效帧数，对齐 FunASR 逻辑)
        T_mel_valid = (len(audio) // 160) + 1
        T_lfr_valid = (T_mel_valid + 5) // 6
        olens_1 = 1 + (T_lfr_valid - 3 + 2) // 2
        target_len = (1 + (olens_1 - 3 + 2) // 2 - 1) // 2 + 1
        
        audio_embd = adaptor_raw[0, :target_len, :].astype(np.float32)
        
        return audio_embd, enc_output
