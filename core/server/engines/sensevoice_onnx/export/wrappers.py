import torch
import torch.nn as nn
from .model import SenseVoiceEncoderSmall

class EncoderExportWrapper(nn.Module):
    """
    SenseVoice Encoder 导出包装器 (集成 Embedding 版)
    支持输入:
        - speech_feat: (Batch, T, 560) -> 原始 Fbank 特征
        - mask: (Batch, T) -> 特征有效掩码 (1代表有效, 0代表填充)
        - prompt_ids: (Batch, 4) -> 4 个提示词 ID (int64)
    """
    def __init__(self, encoder: SenseVoiceEncoderSmall, embed_weight: torch.Tensor):
        super().__init__()
        self.encoder = encoder
        # 将权重集成进模型
        self.embed = nn.Embedding.from_pretrained(embed_weight)

    def forward(self, speech_feat: torch.Tensor, mask: torch.Tensor, prompt_ids: torch.Tensor):
        # 1. 内部查表获取 Prompt Embedding -> (Batch, 4, 512)
        prompt_feat = self.embed(prompt_ids)

        # 2. 拼接 Prompt 与语音特征 -> (Batch, 4 + T, 512)
        x = torch.cat([prompt_feat, speech_feat], dim=1)

        # 3. 构造完整的 Mask
        batch_size = mask.size(0)
        prompt_mask = torch.ones((batch_size, 4), device=mask.device, dtype=mask.dtype)
        full_mask = torch.cat([prompt_mask, mask], dim=1)

        # 4. 调用编码器
        encoder_out = self.encoder(x, full_mask)

        return encoder_out

class CTCExportWrapper(nn.Module):
    """
    SenseVoice CTC 解码头导出包装器 (TopK 优化版)
    输入:
        - enc_out: (Batch, T_plus_4, 512)
    输出:
        - topk_log_probs: (Batch, T_plus_4, 100) -> 前 100 个最大对数概率
        - topk_indices: (Batch, T_plus_4, 100) -> 对应的字符 ID
    """
    def __init__(self, ctc, k=100):
        super().__init__()
        self.ctc = ctc
        self.k = k

    def forward(self, enc_out: torch.Tensor):
        # 1. 计算全量 Log Softmax
        log_probs = self.ctc.log_softmax(enc_out)
        
        # 2. 在 GPU 侧直接提取 TopK
        # 这将极大减少 DML 的回传数据量 (1.2M -> 5KB)
        topk_log_probs, topk_indices = torch.topk(log_probs, self.k, dim=-1)
        
        return topk_log_probs, topk_indices.to(torch.int32)
