# coding: utf-8
"""
录音状态指示浮窗

在屏幕角落显示一个小浮窗：
- 录音中：红色声波竖条跳动
- 转写中：蓝色圆弧转圈
- 识别结果回来后自动隐藏

实现要点：
- 复用 ToastMessageManager 已经在子线程里跑起来的 tkinter root，
  绝不在本模块里新建 tk.Tk() / mainloop，避免双主循环冲突。
- 所有 tk 操作都通过 root.after(0, ...) 投递到 tk 线程执行。
- 任何异常都吞掉，绝不影响录音流程。
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional

import tkinter as tk


# 浮窗尺寸与位置
_WIN_W = 130
_WIN_H = 64
_MARGIN_X = 48      # 距屏幕右边
_MARGIN_BOTTOM = 90  # 距屏幕底部（给任务栏留空间）

# 动画参数
_TICK_MS = 80       # 帧间隔
_BAR_COUNT = 7      # 声波竖条数量
_BAR_GAP = 11
_BAR_W = 5
_RECORD_COLOR = "#ff4d4f"
_TRANSCRIBE_COLOR = "#4096ff"
_BG_COLOR = "#1f1f1f"


class RecordingIndicator:
    """录音状态指示浮窗（单例）"""

    _instance: Optional["RecordingIndicator"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RecordingIndicator":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._root: Optional[tk.Tk] = None
        self._win: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._mode: Optional[str] = None   # 'recording' / 'transcribing' / None
        self._after_id: Optional[str] = None
        self._frame: int = 0
        self._root_ready = threading.Event()

        # 预热：触发 ToastMessageManager 单例创建，让 tk 线程尽早起来。
        # 这样第一次录音时 root 已经就绪，不会在热路径上阻塞事件循环。
        try:
            from .toast_manager import ToastMessageManager
            mgr = ToastMessageManager()
            # 后台线程等待 root 在子线程里被赋值
            threading.Thread(
                target=self._wait_root,
                args=(mgr,),
                daemon=True,
                name="IndicatorRootWaiter",
            ).start()
        except Exception:
            # toast 系统起不来就算了，指示窗直接不可用
            pass

    def _wait_root(self, mgr) -> None:
        """在后台线程等待 toast manager 的 root 创建完成"""
        t0 = time.time()
        while time.time() - t0 < 5.0:
            if mgr.root is not None:
                self._root = mgr.root
                self._root_ready.set()
                return
            time.sleep(0.02)

    # ---------- 外部公开 API（线程安全，可从任意线程调用） ----------

    def show_recording(self) -> None:
        """进入录音状态：红色声波跳动"""
        self._post(lambda: self._show("recording"))

    def show_transcribing(self) -> None:
        """进入转写状态：蓝色圆弧转圈"""
        self._post(lambda: self._show("transcribing"))

    def hide(self) -> None:
        """隐藏浮窗"""
        self._post(self._hide)

    # ---------- 内部实现 ----------

    def _post(self, fn) -> None:
        """把函数投递到 tk 线程执行"""
        # 等 root 就绪（最多等 1 秒，避免卡死录音流程）
        if not self._root_ready.wait(timeout=1.0):
            return
        root = self._root
        if root is None:
            return
        try:
            root.after(0, fn)
        except Exception:
            pass

    def _show(self, mode: str) -> None:
        """在 tk 线程内切换显示状态"""
        try:
            # 取消上一帧定时器
            self._cancel_tick()

            # 创建窗口（如果还没建）
            if self._win is None or not self._win.winfo_exists():
                self._create_window()
            if self._win is None:
                return

            self._mode = mode
            self._frame = 0
            self._win.deiconify()
            self._win.lift()
            self._tick()
        except Exception:
            pass

    def _create_window(self) -> None:
        root = self._root
        if root is None:
            return
        win = tk.Toplevel(root)
        win.overrideredirect(True)           # 去掉标题栏边框
        win.attributes("-topmost", True)    # 置顶
        try:
            win.attributes("-disabled", False)
        except Exception:
            pass

        # 计算位置：屏幕右下角
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = sw - _WIN_W - _MARGIN_X
        y = sh - _WIN_H - _MARGIN_BOTTOM
        win.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")

        canvas = tk.Canvas(
            win, width=_WIN_W, height=_WIN_H,
            bg=_BG_COLOR, highlightthickness=0,
        )
        canvas.pack()

        self._win = win
        self._canvas = canvas

    def _cancel_tick(self) -> None:
        if self._after_id is not None and self._root is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None

    def _tick(self) -> None:
        """动画帧回调"""
        try:
            c = self._canvas
            if c is None:
                return
            c.delete("all")

            cx = _WIN_W // 2
            cy = _WIN_H // 2

            if self._mode == "recording":
                self._draw_wave(c, cx, cy)
            elif self._mode == "transcribing":
                self._draw_spinner(c, cx, cy)

            self._frame += 1
            self._after_id = self._root.after(_TICK_MS, self._tick)
        except Exception:
            pass

    def _draw_wave(self, c: tk.Canvas, cx: int, cy: int) -> None:
        """画跳动的声波竖条"""
        total_w = (_BAR_COUNT - 1) * _BAR_GAP
        x0 = cx - total_w // 2
        for i in range(_BAR_COUNT):
            # 每根竖条用不同相位，形成波浪感
            phase = self._frame * 0.35 + i * 0.7
            amp = 6 + 7 * (0.5 + 0.5 * math.sin(phase))
            x = x0 + i * _BAR_GAP
            c.create_rectangle(
                x, cy - amp, x + _BAR_W, cy + amp,
                fill=_RECORD_COLOR, outline="",
            )
        # 下方小标签
        c.create_text(
            cx, _WIN_H - 12, text="录音中",
            fill="#cccccc", font=("Microsoft YaHei UI", 8),
        )

    def _draw_spinner(self, c: tk.Canvas, cx: int, cy: int) -> None:
        """画转圈的圆弧 loading"""
        r = 16
        start = (self._frame * 22) % 360
        c.create_arc(
            cx - r, cy - r - 4, cx + r, cy + r - 4,
            start=start, extent=270,
            style="arc", outline=_TRANSCRIBE_COLOR, width=4,
        )
        c.create_text(
            cx, _WIN_H - 12, text="识别中",
            fill="#cccccc", font=("Microsoft YaHei UI", 8),
        )

    def _hide(self) -> None:
        try:
            self._cancel_tick()
            self._mode = None
            if self._win is not None and self._win.winfo_exists():
                self._win.withdraw()
        except Exception:
            pass


# ============================================================
# 模块级便捷函数
# ============================================================

_indicator: Optional[RecordingIndicator] = None


def _get() -> RecordingIndicator:
    global _indicator
    if _indicator is None:
        _indicator = RecordingIndicator()
    return _indicator


def show_recording() -> None:
    try:
        _get().show_recording()
    except Exception:
        pass


def show_transcribing() -> None:
    try:
        _get().show_transcribing()
    except Exception:
        pass


def hide() -> None:
    try:
        _get().hide()
    except Exception:
        pass
