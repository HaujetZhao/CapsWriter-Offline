
# coding: utf-8
"""
上下文菜单处理模块

提供托盘菜单"编辑上下文"的回调处理逻辑。
"""

import queue
import threading
import tkinter as tk
from typing import Optional

from config_client import ClientConfig as Config
from util.client.state import console
from . import logger



# 全局对话框管理器
_dialog_manager: Optional['_ContextDialogManager'] = None
_manager_lock = threading.Lock()


def get_dialog_manager() -> Optional['_ContextDialogManager']:
    """获取对话框管理器单例"""
    global _dialog_manager
    with _manager_lock:
        if _dialog_manager is None:
            _dialog_manager = _ContextDialogManager()
        return _dialog_manager


def on_edit_context():
    """
    处理"编辑上下文"菜单点击
    """
    try:
        # 获取对话框管理器并显示对话框
        manager = get_dialog_manager()
        
        # 传递当前的上下文配置作为默认值
        result = manager.show_dialog(default_text=Config.context)

        if not result or not result.confirmed:
            logger.info("用户取消编辑上下文")
            return

        context_text = result.data.get('context', '').strip()

        # 更新配置
        Config.context = context_text
        
        # 显示成功提示
        console.print(f'[green]✓[/] 上下文已更新: {context_text}')
        if context_text:
             logger.info(f"用户更新了上下文: {context_text}")
        else:
             logger.info("用户清空了上下文")

    except Exception as e:
        logger.error(f"处理'编辑上下文'时发生错误: {e}", exc_info=True)
        console.print(f'[red]编辑上下文失败: {e}[/]')


class _ContextDialogManager:
    """
    上下文对话框管理器
    """

    def __init__(self):
        self.request_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self.root: Optional[tk.Tk] = None
        self.is_running = False

        # 在独立线程中启动 Tkinter
        self.tk_thread = threading.Thread(
            target=self._run_tkinter,
            daemon=True,
            name="ContextDialogThread"
        )
        self.tk_thread.start()

        # 等待 Tkinter 初始化完成
        self._wait_for_ready()

    def _wait_for_ready(self, timeout=5.0):
        """等待 Tkinter 线程准备就绪"""
        import time
        start = time.time()
        while not self.is_running and (time.time() - start) < timeout:
            time.sleep(0.05)

        if not self.is_running:
            raise RuntimeError("Context Tkinter 线程启动超时")

    def _run_tkinter(self):
        """在独立线程中运行 Tkinter 主循环"""
        self.root = tk.Tk()
        self.root.withdraw()

        # 设置窗口关闭时的行为
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 标记为运行中
        self.is_running = True

        # 开始处理请求队列
        self._process_requests()

        # 启动 Tkinter 主循环
        self.root.mainloop()

    def _on_close(self):
        """关闭窗口并退出"""
        self.is_running = False
        if self.root:
            self.root.quit()

    def _process_requests(self):
        """处理队列中的对话框请求"""
        if not self.is_running:
            return

        try:
            while not self.request_queue.empty():
                try:
                    req_data = self.request_queue.get_nowait()
                    self._show_dialog_impl(req_data)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"处理上下文对话框请求时发生错误: {e}", exc_info=True)

        if self.root:
            self.root.after(100, self._process_requests)

    def _show_dialog_impl(self, default_text):
        """实际显示对话框"""
        try:
            from util.ui.context_dialog import show_context_dialog

            result = show_context_dialog(
                default_text=default_text,
                parent=self.root,
                title="编辑上下文"
            )
            self.result_queue.put(result)

        except Exception as e:
            logger.error(f"显示上下文对话框时发生错误: {e}", exc_info=True)
            self.result_queue.put(None)

    def show_dialog(self, default_text: str = "") -> Optional[object]:
        """显示对话框"""
        self.request_queue.put(default_text)

        try:
            result = self.result_queue.get(timeout=300)
            return result
        except queue.Empty:
            logger.error("上下文对话框操作超时")
            return None
