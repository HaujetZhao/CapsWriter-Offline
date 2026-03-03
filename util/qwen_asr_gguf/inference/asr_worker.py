# coding=utf-8
import os
from .. import logger
from .schema import MsgType, StreamingMessage, ASREngineConfig
from .encoder import QwenAudioEncoder
from .aligner import QwenForcedAligner

def do_encode_task(msg, encoder, from_enc_q):
    """处理音频编码任务"""
    audio_embd, encode_time = encoder.encode(msg.data)
    from_enc_q.put(StreamingMessage(
        msg_type=MsgType.MSG_EMBD, 
        data=audio_embd, 
        is_last=msg.is_last, 
        encode_time=encode_time
    ))

def do_align_task(msg, aligner, from_align_q):
    """处理时间戳对齐任务"""
    if aligner is None:
        from_align_q.put(StreamingMessage(MsgType.MSG_ALIGN, data=None))
        return

    try:
        res = aligner.align(
            msg.data, 
            msg.text, 
            language=msg.language, 
            offset_sec=msg.offset_sec
        )
        from_align_q.put(StreamingMessage(
            msg_type=MsgType.MSG_ALIGN, 
            data=res, 
            is_last=msg.is_last
        ))
    except Exception as e:
        print(f"[ASRWorker] 对齐出错: {e}")
        from_align_q.put(StreamingMessage(MsgType.MSG_ALIGN, data=None))

def asr_helper_worker_proc(to_worker_q, from_enc_q, from_align_q, config: ASREngineConfig):
    """ASR 辅助进程：同步处理任务，但分流结果回复 (一进两出架构)"""
    
    # 1. 资源初始化
    try:
        # Split Model Paths
        frontend_path = os.path.join(config.model_dir, config.encoder_frontend_fn)
        backend_path = os.path.join(config.model_dir, config.encoder_backend_fn)
        
        # 初始化 Split Encoder
        encoder = QwenAudioEncoder(
            frontend_path=frontend_path,
            backend_path=backend_path,
            use_dml=config.use_dml,
            warmup_sec=config.chunk_size,
            verbose=False
        )
        
        aligner = None
        if config.enable_aligner and config.align_config:
            from .aligner import QwenForcedAligner
            aligner = QwenForcedAligner(config.align_config)
            
        from_enc_q.put(StreamingMessage(MsgType.MSG_READY))
    except Exception as e:
        logger.error(f"[ASRWorker] 模型加载出错：\n{e}")
        from_enc_q.put(StreamingMessage(MsgType.MSG_ERROR, data=e))
        return

    # 2. 统一任务循环
    while True:
        msg: StreamingMessage = to_worker_q.get()
        
        if msg.msg_type == MsgType.CMD_STOP:
            from_enc_q.put(StreamingMessage(MsgType.MSG_DONE))
            from_align_q.put(StreamingMessage(MsgType.MSG_DONE))
            break
            
        if msg.msg_type == MsgType.CMD_ENCODE:
            do_encode_task(msg, encoder, from_enc_q)
            
        elif msg.msg_type == MsgType.CMD_ALIGN:
            do_align_task(msg, aligner, from_align_q)
