# coding: utf-8
"""
语音识别处理模块

处理音频片段的识别、去重和拼接。支持两种拼接策略：
1. text (简单拼接): 基于文本重叠匹配，不依赖时间戳
2. text_accu (精确拼接): 基于时间戳去重，用于字幕生成
"""

import re
import time
from core.server.state import WorkerState, console
from core.server.schema import Task, Result
from core.server.formatter import TextFormatter
from config_server import ServerConfig as Config
from core.tools.token_sync import sync_tokens_from_text
from core.server.engines.base import EngineCapabilities
from .audio import process_audio_task
from . import logger

# 导入拆分后的算法子包
from core.server.merger import (
    merge_by_text,
    merge_tokens_by_sequence_matcher,
    process_tokens_safely,
    tokens_to_text,
)


class TaskPipeline:
    """
    语音识别处理流水线
    
    统筹核心 ASR 引擎、标点模型和对齐器插件的协作。
    基于任务源（mic/file）和引擎能力（Capabilities）自适应调整流水线深度。
    """

    def __init__(self, recognizer, punc_model=None, aligner=None, state: WorkerState = None):
        self.recognizer = recognizer
        self.punc_model = punc_model
        self.aligner = aligner
        self.formatter = TextFormatter(punc_model)
        self.state = state or WorkerState()

    def _process_simple_merge(self, result: Result, stream_result_text: str) -> None:
        """ 处理简单文本拼接（主要输出，用于语音输入） """
        try:
            segment_text = stream_result_text.replace('@@', '').strip()
            segment_text = re.sub(r'\s+', ' ', segment_text)
            
            prev_len = len(result.text)
            result.text = merge_by_text(result.text, segment_text)
            added_chars = len(result.text) - prev_len
            
            logger.debug(f"简单拼接: +{added_chars} 字符, 片段={len(segment_text)}, 总={len(result.text)}")
        except Exception as e:
            logger.warning(f"简单文本拼接失败: {e}")

    def process(self, task: Task) -> Result:
        """
        处理单个音频任务片段并返回识别结果
        """
        try:
            logger.info(f"任务 {task.task_id[:8]}, 语言={task.language}, 类型={task.type}")
            is_first_segment = task.task_id not in self.state.sessions
            session = self.state.get_session(task.task_id, task.socket_id, task.type)
            result = session.result

            # GPU 加速活跃时间更新（只要有任务进来就刷新）
            if Config.gpu_boost_enabled and self.state.gpu_boosted:
                self.state.gpu_last_active = time.time()

            # 2. 预处理音频并获取采样点
            samples = process_audio_task(task, result)

            # 空音频或极短音频，跳过推理直接返回
            if samples is None:
                result.time_start, result.time_submit = task.time_start, task.time_submit
                result.time_complete = time.time()
                result.is_final = task.is_final
                return result

            # 3. 执行识别推理
            stream = self.recognizer.create_stream()
            stream.accept_waveform(task.samplerate, samples)
            self.recognizer.decode_stream(stream, context=task.context, language=task.language)

            # 更新基础时序
            result.time_start, result.time_submit = task.time_start, task.time_submit
            result.time_complete = time.time()

            # 4. 路径 A: 简单文本拼接 (主要用于实时回显)
            asr_raw_text = stream.result.text
            logger.info(f'模型输出：{asr_raw_text}')
            console.print(f'\033[0G  模型输出：[cyan]{asr_raw_text}', soft_wrap=True)
            self._process_simple_merge(result, asr_raw_text)

            # 5. 路径 B: 对齐增强 (仅针对文件任务)
            # 门控：仅在“文件任务”且“引擎不支持时间戳”时，才调用外部 Aligner
            caps = self.recognizer.capabilities
            if (task.type == 'file'
                and EngineCapabilities.TIMESTAMPS not in caps 
                and self.aligner 
                and stream.result.text.strip()):
                
                logger.debug(f"🚩 [Pipeline] 正在对文件分片执行对齐补齐...")
                align_res = self.aligner.align(audio=samples, text=stream.result.text, language=task.language, offset_sec=0.0)
                if align_res and align_res.items:
                    stream.result.tokens = [it.text for it in align_res.items]
                    stream.result.timestamps = [it.start_time for it in align_res.items]


            # 6. 精确 Token 级拼接 (即便没有对齐器，原生支持时间戳的模型也会走这里)
            new_tokens = process_tokens_safely(stream.result.tokens)
            new_timestamps = list(stream.result.timestamps)
            
            result.tokens, result.timestamps = merge_tokens_by_sequence_matcher(
                prev_tokens=result.tokens,
                prev_timestamps=result.timestamps,
                new_tokens=new_tokens,
                new_timestamps=new_timestamps,
                offset=task.offset,
                overlap=task.overlap,
                is_first_segment=is_first_segment
            )
            
            # 7. 生成精确文本结果 (text_accu)
            result.text_accu = tokens_to_text(result.tokens)

            # 8. 最终阶段处理 (任务结束时的格式化)
            if not task.is_final:
                return result

            # 任务结束清理与最终格式化
            raw_text = result.text
            result.text = self.formatter.format(result.text)
            result.text_accu = self.formatter.format(result.text_accu)
            console.print(f'  片段拼接：[purple]{raw_text}', soft_wrap=True)
            console.print(f'  格式化后：[green]{result.text}\n', soft_wrap=True)

            logger.debug(f'格式调整：{raw_text} --> {result.text}')

            # 将格式化引入的标点同步回 token 序列
            if result.tokens and result.text_accu:
                result.tokens, result.timestamps = sync_tokens_from_text(
                    result.tokens, result.timestamps, result.text_accu
                )
            
            # 如果依然没有 tokens (麦克风跳过了对齐)，则用 text 回退
            if not result.tokens and result.text:
                result.text_accu = result.text
                chars = list(result.text_accu.replace(' ', ''))
                if chars and result.duration > 0:
                    t_per_char = result.duration / len(chars)
                    result.tokens, result.timestamps = chars, [i * t_per_char for i in range(len(chars))]
            
            result.is_final = True
            
            # 打印统计
            process_time = result.time_complete - task.time_submit
            rtf = process_time / result.duration if result.duration > 0 else 0
            logger.info(f"任务完成: {task.task_id[:8]}, 时长={result.duration:.2f}s, 耗时={process_time:.3f}s, RTF={rtf:.3f}")

            return result

        except Exception as e:
            logger.error(f"推理管线错误: {e}", exc_info=True)
            raise



