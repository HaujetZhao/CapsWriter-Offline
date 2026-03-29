# coding=utf-8
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

class Qwen3ASRFrontendAtomicOnnx(nn.Module):
    """
    Qwen3-ASR 原子前端 (Atomic Frontend)
    只处理单个 100 帧的 Chunk (100 * 10ms = 1s)，无状态，极低显存。
    外部 Python 循环负责调度。
    """
    def __init__(self, audio_tower):
        super().__init__()
        self.conv2d1 = audio_tower.conv2d1
        self.conv2d2 = audio_tower.conv2d2
        self.conv2d3 = audio_tower.conv2d3
        self.conv_out = audio_tower.conv_out
        # 注册位置编码表
        self.register_buffer("pos_embed_table", audio_tower.positional_embedding.positional_embedding)
        
    def forward(self, chunk: torch.Tensor):
        """
        chunk: (1, 128, 100) - 必须是 float32
        """
        # 1. 2D 卷积 (标准处理, Batch=1)
        x = chunk.unsqueeze(1) # (1, 1, 128, 100)
        x = F.gelu(self.conv2d1(x))
        x = F.gelu(self.conv2d2(x))
        x = F.gelu(self.conv2d3(x))
        
        # 2. 展平与投影
        # 输出 T 维度固定为 13 (100 -> 13)
        x = x.permute(0, 3, 1, 2).contiguous().flatten(2) # (1, 13, D_conv)
        x = self.conv_out(x) # (1, 13, D_model)
        
        # 3. 相对循环位置编码 (Relative Cyclic Positional Embedding)
        # 根据旧版验证通过的逻辑 ((cumsum - 1) % 13)，位置编码是循环的[0..12]。
        # 现在的实现完全不依赖 chunk_idx，对任何 chunk 都是加同样的位置编码。
        
        # 使用 arange 生成 0..12
        local_indices = torch.arange(13, device=x.device, dtype=torch.long)
        
        # 使用 embedding 查找
        pos_embed = F.embedding(local_indices, self.pos_embed_table).unsqueeze(0)
        x = x + pos_embed
        
        return x

class Qwen3ASRAudioAttentionOnnx(nn.Module):
    """
    Qwen3-ASR 多头注意力 (DML 友好 + 符号追踪修复版)
    """
    def __init__(self, raw_attn):
        super().__init__()
        self.num_heads = raw_attn.num_heads
        self.head_dim = raw_attn.head_dim
        self.scaling = raw_attn.scaling
        self.q_proj = raw_attn.q_proj
        self.k_proj = raw_attn.k_proj
        self.v_proj = raw_attn.v_proj
        self.out_proj = raw_attn.out_proj

    def forward(self, hidden_states, attention_mask=None):
        b, t, d = hidden_states.shape
        # 使用 unflatten/transpose 替代 view 
        # 经验文档建议：在 DML 中尽量保持 Batch=1 
        q = self.q_proj(hidden_states).unflatten(-1, (self.num_heads, self.head_dim)).transpose(1, 2)
        k = self.k_proj(hidden_states).unflatten(-1, (self.num_heads, self.head_dim)).transpose(1, 2)
        v = self.v_proj(hidden_states).unflatten(-1, (self.num_heads, self.head_dim)).transpose(1, 2)
        
        attn_weights = torch.matmul(q, k.transpose(-1, -2)) * self.scaling
        
        if attention_mask is not None:
            # 依据经验文档 4.2 节：使用 Additive Masking 替代昂贵的 masked_fill
            # DML 对 Add 算子的融合效果显著优于 Where (masked_fill)
            attn_weights = attn_weights + attention_mask
            
        attn_weights = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(q.dtype)
        attn_output = torch.matmul(attn_weights, v)
        
        # 展平输出
        attn_output = attn_output.transpose(1, 2).contiguous().flatten(2)
        attn_output = self.out_proj(attn_output)
        return attn_output

class Qwen3ASRBackendOnnx(nn.Module):
    def __init__(self, audio_tower):
        super().__init__()
        self.layers = nn.ModuleList()
        for raw_layer in audio_tower.layers:
            raw_layer.self_attn = Qwen3ASRAudioAttentionOnnx(raw_layer.self_attn)
            self.layers.append(raw_layer)
        self.ln_post = audio_tower.ln_post
        self.proj1 = audio_tower.proj1
        self.act = audio_tower.act
        self.proj2 = audio_tower.proj2
        
    def forward(self, hidden_states, attention_mask: Optional[torch.Tensor] = None):
        for layer in self.layers:
            residual = hidden_states
            hidden_states = layer.self_attn_layer_norm(hidden_states)
            hidden_states = layer.self_attn(hidden_states, attention_mask=attention_mask)
            hidden_states = residual + hidden_states
            residual = hidden_states
            hidden_states = layer.final_layer_norm(hidden_states)
            hidden_states = layer.fc1(hidden_states)
            hidden_states = layer.activation_fn(hidden_states)
            hidden_states = layer.fc2(hidden_states)
            hidden_states = residual + hidden_states
        hidden_states = self.ln_post(hidden_states)
        hidden_states = self.proj1(hidden_states)
        hidden_states = self.act(hidden_states)
        hidden_states = self.proj2(hidden_states)
        return hidden_states

class Qwen3ASREncoderFullOnnx(nn.Module):
    def __init__(self, audio_tower):
        super().__init__()
        self.frontend = Qwen3ASRFrontendFullOnnx(audio_tower)
        self.backend = Qwen3ASRBackendOnnx(audio_tower)
        
    def forward(self, input_features: torch.Tensor, attention_mask: Optional[torch.Tensor] = None):
        hidden_states = self.frontend(input_features)
        last_hidden_state = self.backend(hidden_states, attention_mask=attention_mask)
        return last_hidden_state
