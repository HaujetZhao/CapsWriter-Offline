# coding: utf-8
"""
识别任务处理器

负责监听任务队列、执行识别流水线并将结果返回主进程。
"""

from multiprocessing import Queue
from util.server.pipeline import recognize
from . import logger


class TaskHandler:
    """
    任务处理器
    
    协调输入输出队列与识别引擎之间的任务流。
    """
    def __init__(self, queue_in: Queue, queue_out: Queue, sockets_id):
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
        
        # 引擎实例 (由主 Worker 注入)
        self.recognizer = None
        self.punc_model = None
        self.aligner = None

    def set_engine(self, recognizer, punc_model=None, aligner=None):
        """注入识别引擎实例"""
        self.recognizer = recognizer
        self.punc_model = punc_model
        self.aligner = aligner

    def loop(self):
        """
        核心任务循环
        
        阻塞监听队列，执行识别并返回结果。
        """
        logger.info("TaskHandler 开始工作循环")
        
        while True:
            try:
                # 1. 阻塞获取任务 (1秒超时以便响应退出信号)
                task = self.queue_in.get(timeout=1)
            except:
                # 可能是超时，继续循环
                continue

            # 2. 检查退出信号 (None)
            if task is None:
                logger.info("TaskHandler 收到退出信号 (None)")
                break

            # 3. 检查任务关联的连接是否依然存活
            if task.socket_id not in self.sockets_id:
                logger.debug(f"任务连接已断开，跳过处理: {task.task_id[:8]}")
                continue

            # 4. 执行识别流程
            try:
                # 调用 pipeline.py 中的主逻辑
                result = recognize(self.recognizer, self.punc_model, task, self.aligner)
                
                # 5. 返回识别结果给主进程
                self.queue_out.put(result)
                
            except Exception as e:
                logger.error(f"任务执行出错: {str(e)}", exc_info=True)
                # 即使单个任务出错，也不退出循环，防止 Worker 进程崩溃

        logger.info("TaskHandler 工作循环结束")
