# coding: utf-8
"""
热词菜单处理模块

提供托盘菜单"添加热词"的回调处理逻辑。
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional

from util.client.state import get_state, console
from util.logger import get_logger

logger = get_logger('client')


# 全局对话框管理器
_dialog_manager: Optional['_HotwordDialogManager'] = None
_manager_lock = threading.Lock()


def get_dialog_manager() -> Optional['_HotwordDialogManager']:
    """获取对话框管理器单例"""
    global _dialog_manager
    with _manager_lock:
        if _dialog_manager is None:
            _dialog_manager = _HotwordDialogManager()
        return _dialog_manager


def on_add_hotword():
    """
    处理"添加热词"菜单点击
    """
    try:
        # 获取对话框管理器并显示对话框
        manager = get_dialog_manager()
        result = manager.show_dialog()

        if not result:
            logger.info("用户取消添加热词")
            return

        hotword_text = result.get('hotword', '').strip()

        if not hotword_text:
            logger.warning("用户提交了空的热词")
            return

        # 保存到 hot.txt
        _save_hotwords(hotword_text)

        # 显示成功提示
        console.print(f'[green]✓[/] 热词已添加: {hotword_text}')

    except Exception as e:
        logger.error(f"处理'添加热词'时发生错误: {e}", exc_info=True)
        console.print(f'[red]添加热词失败: {e}[/]')


def _save_hotwords(text: str) -> None:
    """
    保存热词到 hot.txt

    Args:
        text: 热词文本（支持多行）
    """
    hot_file = Path('hot.txt')
    
    # 确保文件存在
    if not hot_file.exists():
        hot_file.touch()

    # 读取现有内容，检查最后是否有换行
    content = hot_file.read_text(encoding='utf-8')
    needs_newline = content and not content.endswith('\n')

    # 追加记录到文件
    with open(hot_file, 'a', encoding='utf-8') as f:
        if needs_newline:
            f.write('\n')
        
        # 处理每一行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            f.write(f"{line}\n")

    logger.debug(f"已追加 {len(lines)} 个热词到 {hot_file}")


class _HotwordDialogManager:
    """
    热词对话框管理器
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
            name="HotwordDialogThread"
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
            raise RuntimeError("Hotword Tkinter 线程启动超时")

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
                    self.request_queue.get_nowait()
                    self._show_dialog_impl()
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"处理热词对话框请求时发生错误: {e}", exc_info=True)

        if self.root:
            self.root.after(100, self._process_requests)

    def _show_dialog_impl(self):
        """实际显示对话框"""
        try:
            from util.ui.hotword_dialog import show_hotword_dialog

            result = show_hotword_dialog(
                parent=self.root,
                title="添加热词"
            )
            self.result_queue.put(result)

        except Exception as e:
            logger.error(f"显示热词对话框时发生错误: {e}", exc_info=True)
            self.result_queue.put(None)

    def show_dialog(self) -> Optional[tuple]:
        """显示对话框"""
        self.request_queue.put(True)

        try:
            result = self.result_queue.get(timeout=300)
            return result
        except queue.Empty:
            logger.error("热词对话框操作超时")
            return None
