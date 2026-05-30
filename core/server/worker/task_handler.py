# coding: utf-8
"""
识别任务处理器

负责监听任务队列、执行识别流水线并将结果返回主进程。

公平调度：从不同客户端（socket）轮转取任务处理，防止文件转录淹没队列。
同 socket 内保持 FIFO 顺序，跨 socket 间轮转调度。
"""

from collections import OrderedDict, deque
from multiprocessing import Queue
from multiprocessing.managers import ListProxy
import queue
from .pipeline import TaskPipeline
from ..state import WorkerState
from .gpu_boost import GpuBoostManager
from . import logger


class TaskBuffer:
    """按 task_id 分组缓冲，支持跨 session 轮转出队。"""
    def __init__(self, state: WorkerState):
        self.state = state
        self._buffers: OrderedDict[str, deque] = OrderedDict()

    def enqueue(self, task):
        """将任务放入对应 task_id 的缓冲尾部（同 session 内 FIFO）。
        首次遇到新 task_id 时预创建 session。"""
        tid = task.task_id
        if tid not in self._buffers:
            self._buffers[tid] = deque()
            self.state.get_session(tid, task.socket_id, task.type)
        self._buffers[tid].append(task)

    def pop(self):
        """取出最新 session 的下一个任务。没有待处理任务时返回 None。"""
        if not self._buffers:
            return None

        tid, buf = next(reversed(self._buffers.items()))
        task = buf.popleft()

        if not buf:
            del self._buffers[tid]

        return task

    def cleanup_tasks(self):
        """清理已断开连接的 session 的缓冲任务。"""
        for tid in list(self._buffers):
            if tid not in self.state.sessions:
                logger.debug(f"清理断开连接的 session: {tid[:8]}")
                del self._buffers[tid]

    @property
    def is_empty(self) -> bool:
        return len(self._buffers) == 0


class TaskHandler:
    """
    任务处理器

    协调输入输出队列与识别引擎之间的任务流。
    支持跨 socket 公平轮转调度。
    """
    def __init__(self, queue_in: Queue, queue_out: Queue, sockets_id: ListProxy, state: WorkerState):
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.sockets_id = sockets_id
        self.state = state

        self.recognizer = None
        self.punc_model = None
        self.aligner = None
        self.pipeline = None

        self.buffer = TaskBuffer(state)
        self.gpu_boost = GpuBoostManager(state)

    def set_engine(self, recognizer, punc_model=None, aligner=None):
        """注入识别引擎实例并初始化管线"""
        self.recognizer = recognizer
        self.punc_model = punc_model
        self.aligner = aligner
        self.pipeline = TaskPipeline(recognizer, punc_model, aligner, self.state)

    def drain_queue(self) -> bool:
        """Drain 队列中所有任务到缓冲区。Returns: False = 退出信号。"""
        while True:
            # 获取任务
            try:
                if self.buffer.is_empty:
                    task = self.queue_in.get(timeout=1)
                else:
                    task = self.queue_in.get(timeout=0.02)
            except queue.Empty:
                if self.buffer.is_empty:
                    self.cleanup_engines()
                    continue
                else:
                    return True
            except InterruptedError:
                continue
            
            # 判断退出信号
            if task is None:
                return False

            # 跳过已断开连接客户端的任务
            if task.socket_id not in self.sockets_id:
                logger.debug(f"跳过断连客户端任务: {task.task_id[:8]}")
                continue

            # 任务进入缓冲区
            self.buffer.enqueue(task)

    def cleanup(self):
        """清理断连 socket 的缓冲任务和 session。"""
        self.state.cleanup_sessions(self.sockets_id)
        self.buffer.cleanup_tasks()

    def cleanup_engines(self):
        """闲置资源清理：对齐器卸载 + GPU 加速取消。"""
        if self.pipeline and self.pipeline.aligner:
            self.pipeline.aligner.check_idle()
        self.gpu_boost.check_idle()

    def handle_command_task(self, task):
        """处理命令任务。"""
        self.gpu_boost.handle_command(task)

    def handle_audio_task(self, task):
        """处理音频识别任务。"""
        result = self.pipeline.process(task)
        self.queue_out.put(result)
        if result.is_final:
            self.state.sessions.pop(task.task_id, None)

    def loop(self):
        """核心任务循环：drain 队列 → 清理断连 → 轮转执行一个。"""
        logger.info("TaskHandler 开始工作循环 (公平调度)")

        while True:
            try:
                if not self.drain_queue():
                    break

                task = self.buffer.pop()
                if task is None:
                    continue

                # 根据任务类型分派
                if task.type == 'cmd':
                    self.handle_command_task(task)
                else:
                    self.handle_audio_task(task)

                self.cleanup()
            except InterruptedError:
                continue
            except Exception as e:
                logger.error(f"任务执行出错: {str(e)}", exc_info=True)

        logger.info("TaskHandler 工作循环结束")
