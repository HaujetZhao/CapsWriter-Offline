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
from platform import system

from .model_loader import ModelLoader
from .task_handler import TaskHandler
from . import logger


class RecognizerWorker:
    """
    识别进程工作者 (Facade)
    
    统一调度模型加载器与任务处理器，负责识别进程的完整运行。
    """
    def __init__(self, queue_in: Queue, queue_out: Queue, sockets_id: list, stdin_fn: int = None):
        """
        初始化 Worker
        
        Args:
            queue_in: 输入队列
            queue_out: 输出队列
            sockets_id: 活动连接列表
            stdin_fn: 标准输入文件描述符 (用于 Windows Ctrl+C 接管)
        """
        # 1. 初始化核心组件
        self.loader = ModelLoader()
        self.handler = TaskHandler(queue_in, queue_out, sockets_id)
        
        # 2. 状态追踪
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

    def run(self):
        """
        启动子进程运行
        
        执行全流程：环境配置 -> 加载模型 -> 任务循环。
        """
        if self._is_running:
            return
        
        # 1. 系统环境配置
        self._setup_environment()
        
        # 2. 载入核心识别模型
        try:
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
                from util.tools.empty_working_set import empty_current_working_set
                empty_current_working_set()
            
            # 6. 进入循环
            self._is_running = True
            self.handler.loop()
            
        except Exception as e:
            logger.error(f"Worker 启动失败: {str(e)}", exc_info=True)
            raise e
        finally:
            self.stop()

    def stop(self):
        """统一停止 Worker 并释放资源"""
        if not self._is_running:
            # 防止重复清理
            self.loader.cleanup()
            return

        logger.info("正在停止 Worker 并回收资源...")
        self.loader.cleanup()
        self._is_running = False
        logger.debug("Worker 资源已完成回收")
