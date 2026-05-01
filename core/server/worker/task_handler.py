# coding: utf-8
"""
识别任务处理器

负责监听任务队列、执行识别流水线并将结果返回主进程。
"""

from multiprocessing import Queue
import queue
from .pipeline import TaskPipeline
from ..state import WorkerState
from . import logger


class TaskHandler:
    """
    任务处理器
    
    协调输入输出队列与识别引擎之间的任务流。
    """
    def __init__(self, queue_in: Queue, queue_out: Queue, sockets_id, state: WorkerState):
        """
        初始化处理器
        
        Args:
            queue_in: 任务输入队列
            queue_out: 结果输出队列
            sockets_id: 共享的 Socket ID 列表 (用于连接存活检查)
        """
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.sockets_id = sockets_id
        
        # 引用由门面注入的状态
        self.state = state
        
        # 引擎与管线组件
        self.recognizer = None
        self.punc_model = None
        self.aligner = None
        self.pipeline = None

    def set_engine(self, recognizer, punc_model=None, aligner=None):
        """注入识别引擎实例并初始化管线"""
        self.recognizer = recognizer
        self.punc_model = punc_model
        self.aligner = aligner
        # 初始化持久化管线对象
        self.pipeline = TaskPipeline(recognizer, punc_model, aligner, self.state)

    def loop(self):
        """
        核心任务循环
        """
        logger.info("TaskHandler 开始工作循环")

        while True:
            try:
                task = self.queue_in.get(timeout=1)
            except queue.Empty:
                # 空闲时：清理已断开连接的 session + 检查对齐器是否需要卸载
                self.state.cleanup_stale_sessions(self.sockets_id)
                if self.pipeline and self.pipeline.aligner:
                    if hasattr(self.pipeline.aligner, 'check_idle'):
                        self.pipeline.aligner.check_idle()
                continue
            except InterruptedError:
                continue

            if task is None:
                logger.info("TaskHandler 收到退出信号 (None)")
                break

            if task.socket_id not in self.sockets_id:
                logger.debug(f"任务连接已断开，跳过处理: {task.task_id[:8]}")
                continue

            # 4. 执行识别流程
            try:
                # 使用标准化的管线对象处理任务
                result = self.pipeline.process(task)
                
                # 5. 返回识别结果给主进程
                self.queue_out.put(result)
                
                # 6. 如果任务已结束，清理会话状态
                if result.is_final:
                    self.state.sessions.pop(task.task_id, None)
                
            except Exception as e:
                logger.error(f"任务执行出错: {str(e)}", exc_info=True)
                # 即使单个任务出错，也不退出循环，防止 Worker 进程崩溃

        logger.info("TaskHandler 工作循环结束")
