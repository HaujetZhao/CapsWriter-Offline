# coding: utf-8
"""
识别子进程管理器 (ProcessManager)

负责维护单机识别进程的生命周期，包括启动、模型加载监控、异常退出捕获。
"""
from __future__ import annotations
import sys
import os
import queue
from multiprocessing import Process, Manager
from typing import TYPE_CHECKING
from ..state import console
from . import start_worker
from .check_model import check_model
from . import logger
if TYPE_CHECKING:
    from ..app import CapsWriterServer


class ProcessManager:
    """
    识别子进程管理器
    
    由 CapsWriterServer 调用，专注于进程层级的控制。
    """
    def __init__(self, app: CapsWriterServer):
        self._process = None
        self.app = app
        self.is_alive = False

    def start(self):
        """
        启动识别子进程并等待模型加载完成
        
        Returns:
            Process: 启动成功的子进程对象
        """
        # 防连续触发
        if self.is_alive: return
        self.is_alive = True

        # 1. 前置检查
        check_model()

        # 2. 初始化共享资源
        # 使用 Manager 管理共享列表，用于追踪活动连接
        state = self.app.state
        state.sockets_id = Manager().list()
        
        # 获取标准输入文件描述符，用于 Windows 下的信号传递补丁
        stdin_fn = sys.stdin.fileno()
        
        # 3. 创建并启动进程
        self._process = Process(
            target=start_worker,
            args=(state.queue_in,
                  state.queue_out,
                  state.sockets_id, 
                  stdin_fn),
            daemon=True
        )
        self._process.start()
        
        # 存入状态以便其他模块引用
        state.recognize_process = self._process
        logger.info(f"识别子进程已拉起 (PID: {self._process.pid})")

        # 4. 等待模型加载完成 (轮询方式)
        self._wait_for_models()
        
        return self._process

    def _wait_for_models(self):
        """轮询队列直到收到模型加载成功 (True) 或发生错误"""
        logger.info("正在等待子进程加载模型...")
        
        while self.is_alive:
            try:
                # 阻塞最多 100ms
                status = self.app.state.queue_out.get(timeout=0.1)
                if status is True:
                    # 收到 True 说明模型加载成功
                    break
            except (queue.Empty, OSError):
                if self._process and not self._process.is_alive():
                    self._handle_unexpected_exit()
                    return
                continue
            
        if not self.is_alive: return
        logger.info("模型加载完成，ASR 服务就绪")
        console.rule('[green3]开始服务')
        console.line()

    def _handle_unexpected_exit(self):
        """处理子进程加载模型时的意外退出"""
        exit_code = self._process.exitcode
        if exit_code != 0:
            logger.error(f"识别子进程意外退出! ExitCode: {exit_code}")
            logger.error("这通常是由于模型损坏、底层库冲突或系统资源不足导致的。")
        
        # 请求主系统同步退出
        self.app.stop()

    def stop(self):
        """停止子进程"""

        # 防连续触发
        if not self.is_alive: return
        self.is_alive = False

        if self._process and self._process.is_alive():
            logger.info(f"正在终止识别子进程 (PID: {self._process.pid})...")
            # 发送 None 任务通知优雅退出 (作为兜底)

            self.app.state.queue_in.put(None)
            
            # 如果 2 秒内没退，则强制 kill
            self._process.join(timeout=2)
            if self._process.is_alive():
                logger.debug("子进程未响应优雅退出，执行强制终止")
                self._process.terminate()
            