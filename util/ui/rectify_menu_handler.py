# coding: utf-8
"""
纠错记录菜单处理模块

提供托盘菜单"添加纠错记录"的回调处理逻辑。
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional

from util.client.state import get_state
from util.client.state import console
from util.logger import get_logger

logger = get_logger('client')


# 全局对话框管理器
_dialog_manager: Optional['_RectifyDialogManager'] = None
_manager_lock = threading.Lock()


def get_dialog_manager() -> Optional['_RectifyDialogManager']:
    """获取对话框管理器单例"""
    global _dialog_manager
    with _manager_lock:
        if _dialog_manager is None:
            _dialog_manager = _RectifyDialogManager()
        return _dialog_manager


def on_add_rectify_record():
    """
    处理"添加纠错记录"菜单点击

    使用独立的 Tkinter 线程运行对话框，避免线程问题。

    流程：
    1. 从 ClientState 获取最近一次的识别结果
    2. 将请求放入对话框管理器的队列
    3. 等待用户输入完成
    4. 保存到 hot-rectify.txt 并触发重载
    """
    try:
        # 1. 从全局状态获取最近一次识别结果
        state = get_state()
        recognition_text = state.last_recognition_text or ""  # 如果为 None，使用空字符串

        logger.info(f"用户点击'添加纠错记录'，识别结果: '{recognition_text[:30]}...'")

        # 2. 获取对话框管理器并显示对话框
        manager = get_dialog_manager()
        result = manager.show_dialog(recognition_text)

        if not result:
            logger.info("用户取消添加纠错记录")
            return

        original, corrected = result

        if not original or not corrected:
            logger.warning("用户提交了空的纠错记录")
            return

        logger.info(f"用户提交纠错记录: original='{original}', corrected='{corrected}'")

        # 3. 保存到 hot-rectify.txt
        _save_rectify_record(original, corrected)

        # 4. 显示成功提示（简洁版本，文件监视器会显示详细信息）
        console.print('[green]✓[/] 纠错规则已添加')

    except Exception as e:
        logger.error(f"处理'添加纠错记录'时发生错误: {e}", exc_info=True)
        console.print(f'[red]添加纠错记录失败: {e}[/]')


def _save_rectify_record(original: str, corrected: str) -> None:
    """
    保存纠错记录到 hot-rectify.txt

    Args:
        original: 原始文本（识别出来的错误文本）
        corrected: 纠错文本（正确的文本）
    """
    rectify_file = Path('hot-rectify.txt')

    # 追加记录到文件
    with open(rectify_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{original}\n{corrected}\n---\n")

    logger.debug(f"已追加纠错记录到 {rectify_file}")


class _RectifyDialogManager:
    """
    纠错对话框管理器

    在独立线程中运行 Tkinter 主循环，通过队列处理对话框请求。
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
            name="RectifyDialogThread"
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
            raise RuntimeError("Tkinter 线程启动超时")

    def _run_tkinter(self):
        """在独立线程中运行 Tkinter 主循环"""
        # 创建隐藏的主窗口
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
        """处理队列中的对话框请求（使用 after 轮询）"""
        if not self.is_running:
            return

        try:
            # 非阻塞检查队列
            while not self.request_queue.empty():
                try:
                    recognition_text = self.request_queue.get_nowait()
                    self._show_dialog_impl(recognition_text)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"处理对话框请求时发生错误: {e}", exc_info=True)

        # 继续轮询（100ms）
        if self.root:
            self.root.after(100, self._process_requests)

    def _show_dialog_impl(self, recognition_text: str):
        """实际显示对话框（在 Tkinter 线程中调用）"""
        try:
            from util.ui.rectify_dialog import show_rectify_dialog

            result = show_rectify_dialog(
                recognition_text=recognition_text,
                parent=self.root,
                title="添加纠错记录"
            )

            # 将结果放入结果队列
            if result and result.confirmed:
                original = result.get('original', '').strip()
                corrected = result.get('corrected', '').strip()
                self.result_queue.put((original, corrected))
            else:
                self.result_queue.put(None)

        except Exception as e:
            logger.error(f"显示对话框时发生错误: {e}", exc_info=True)
            self.result_queue.put(None)

    def show_dialog(self, recognition_text: str) -> Optional[tuple]:
        """
        显示对话框（从任意线程调用）

        Args:
            recognition_text: 识别结果文本

        Returns:
            (original, corrected) 元组，如果用户取消则返回 None
        """
        # 将请求放入队列
        self.request_queue.put(recognition_text)

        # 等待结果
        try:
            result = self.result_queue.get(timeout=300)  # 5分钟超时
            return result
        except queue.Empty:
            logger.error("对话框操作超时")
            return None


if __name__ == "__main__":
    # 测试代码
    from util.client.state import get_state

    # 模拟识别结果
    state = get_state()
    state.last_recognition_text = "原锯子不对"

    # 测试菜单处理
    print("测试菜单处理...")
    on_add_rectify_record()
