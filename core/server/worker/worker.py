# coding: utf-8
"""
识别子进程 Worker 门面类

采用门面模式将复杂的加载、信号、任务处理逻辑进行组合并统一导出。
该模块作为子进程运行的完整生命周期管理者。
"""

import os
import sys
import signal
import atexit
from multiprocessing import Queue
from multiprocessing.managers import ListProxy
from platform import system

from .model_loader import ModelLoader
from .task_handler import TaskHandler
from ..state import WorkerState
from . import logger


class RecognizerWorker:
    """
    识别进程工作者 (Facade)
    
    统一调度模型加载器与任务处理器，负责识别进程的完整运行。
    """
    def __init__(self, queue_in: Queue, queue_out: Queue, sockets_id: ListProxy, stdin_fn: int = None):
        # 1. 初始化核心状态
        self.state = WorkerState()
        
        # 2. 初始化核心组件 (注入 state)
        self.loader = ModelLoader()
        self.handler = TaskHandler(queue_in, queue_out, sockets_id, self.state)
        
        # 3. 状态追踪
        self.stdin_fn = stdin_fn
        self._is_running = False

    def _setup_environment(self):
        """配置运行环境 (输入接管、信号处理、资源回收)"""
        if self.stdin_fn is not None:
            try:
                sys.stdin = os.fdopen(self.stdin_fn)
            except Exception as e:
                logger.warning(f"Worker 无法接管标准输入: {str(e)}")

        # 注册信号处理器 (优雅退出)
        def signal_handler(signum, frame):
            # sig_name = signal.Signals(signum).name
            # logger.info(f"Worker 接收到信号 {sig_name} ({signum})，开始退出...")
            # self.stop()
            # exit(0)
            ...

        # 仅注册主信号
        signal.signal(signal.SIGINT, lambda signum, frame: None)
        
        # atexit 兜底
        atexit.register(self.stop)
        logger.debug("Worker 运行环境配置完成")

    def initialize(self):
        """执行识别子进程环境初始化与模型加载"""
        # 1. 系统环境配置
        self._setup_environment()

        # 2. 载入核心识别模型
        logger.info("Worker 正在加载语音识别模型...")
        self.loader.load()
        
        # 3. 将加载好的引擎委派给处理器
        self.handler.set_engine(
            recognizer=self.loader.recognizer, 
            punc_model=self.loader.punc_model,
            aligner=self.loader.aligner
        )
        
        # 4. 通知主进程模型已加载成功
        self.handler.queue_out.put(True)
        
        # 5. Windows 下物理内存清理 (优化项)
        if system() == 'Windows':
            from core.tools.empty_working_set import empty_current_working_set
            empty_current_working_set()
        
        logger.info("Worker 资源初始化完成")

    def start(self):
        """
        启动子进程任务循环
        """
        if self._is_running:return
        self._is_running = True

        self.initialize()
        
        # 2. 进入循环
        try:
            self.handler.loop()
        except Exception as e:
            logger.error(f"Worker 运行中发生异常: {str(e)}", exc_info=True)
            raise e
        finally:
            self.stop()


    def stop(self):
        """统一停止 Worker 并释放资源"""
        if not self._is_running:return
        self._is_running = False

        logger.info("正在停止 Worker 并回收资源...")
        self.loader.cleanup()
        logger.info("Worker 资源已完成回收")


    def run(self):
        """
        供 multiprocessing 调用
        """
        self.start()
