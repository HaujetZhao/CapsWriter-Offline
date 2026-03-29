# coding: utf-8
"""
识别子进程管理器 (ProcessManager)

负责维护单机识别进程的生命周期，包括启动、模型加载监控、异常退出捕获。
"""

import sys
import os
import queue
import errno
from multiprocessing import Process, Manager
from util.server.context import Context, console
from util.server.worker import start_worker
from util.server.check_model import check_model
from util.tools.lifecycle import lifecycle
from . import logger


class ProcessManager:
    """
    识别子进程管理器
    
    由 CapsWriterServer 调用，专注于进程层级的控制。
    """
    def __init__(self):
        self._process = None

    def start_worker(self):
        """
        启动识别子进程并等待模型加载完成
        
        Returns:
            Process: 启动成功的子进程对象
        """
        # 1. 前置检查
        check_model()

        # 2. 初始化共享资源
        # 使用 Manager 管理共享列表，用于追踪活动连接
        Context.sockets_id = Manager().list()
        
        # 获取标准输入文件描述符，用于 Windows 下的信号传递补丁
        stdin_fn = sys.stdin.fileno()
        
        # 3. 创建并启动进程
        self._process = Process(
            target=start_worker,
            args=(Context.queue_in,
                  Context.queue_out,
                  Context.sockets_id, 
                  stdin_fn),
            daemon=False
        )
        self._process.start()
        
        # 存入全局上下文便于其他模块引用（兼容旧代码）
        Context.recognize_process = self._process
        logger.info(f"识别子进程已拉起 (PID: {self._process.pid})")

        # 4. 等待模型加载完成 (轮询方式)
        self._wait_for_models()
        
        return self._process

    def _wait_for_models(self):
        """轮询队列直到收到模型加载成功 (True) 或发生错误"""
        logger.info("正在等待子进程加载模型...")
        
        while not lifecycle.is_shutting_down:
            try:
                # 阻塞最多 100ms
                status = Context.queue_out.get(timeout=0.1)
                if status is True:
                    # 收到 True 说明模型加载成功
                    break
            except queue.Empty:
                # 检查进程是否还活着
                if not self._process.is_alive():
                    # 进程意外死亡
                    self._handle_unexpected_exit()
                    return
                continue
            except (InterruptedError, OSError) as e:
                # 处理被核心信号中断的情况 (Errno 4)
                if isinstance(e, InterruptedError) or (hasattr(e, 'errno') and e.errno == errno.EINTR):
                    continue
                raise e

        if lifecycle.is_shutting_down:
            logger.warning("在加载模型时收到系统停机指令")
            self.stop()
            return

        logger.info("模型加载完成，ASR 服务就绪")
        console.rule('[green3]开始服务')
        console.line()

    def _handle_unexpected_exit(self):
        """处理子进程加载模型时的意外退出"""
        exit_code = self._process.exitcode
        logger.error(f"识别子进程意外退出! ExitCode: {exit_code}")
        
        if exit_code != 0:
            logger.error("这通常是由于模型损坏、底层库冲突或系统资源不足导致的。")
        
        # 请求主系统同步退出
        lifecycle.request_shutdown()

    def stop(self):
        """停止子进程"""
        if self._process and self._process.is_alive():
            logger.info(f"正在终止识别子进程 (PID: {self._process.pid})...")
            # 发送 None 任务通知优雅退出 (作为兜底)
            try:
                Context.queue_in.put(None)
            except:
                pass
            
            # 如果 2 秒内没退，则强制 kill
            self._process.join(timeout=2)
            if self._process.is_alive():
                logger.debug("子进程未响应优雅退出，执行强制终止")
                self._process.terminate()
            
        self._process = None
