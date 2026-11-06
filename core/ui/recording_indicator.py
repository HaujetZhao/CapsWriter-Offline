import tkinter as tk
import random
import threading

class RecordingIndicator:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.root = None
        self.window = None
        self.canvas = None
        self.state = "idle"  # idle / recording / recognizing
        self._anim_job = None
        self._bar_count = 7
        self._bar_heights = [20] * self._bar_count
        self._arc_angle = 0

    def _get_root(self):
        if self.root is None:
            try:
                from core.ui.toast_manager import ToastMessageManager
                self.root = ToastMessageManager.get_instance().root
            except Exception:
                self.root = tk._default_root
        return self.root

    def _create_window(self):
        if self.window is not None:
            return
        root = self._get_root()
        if root is None:
            return

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.9)
        self.window.configure(bg="#1e1e1e")

        self.canvas = tk.Canvas(
            self.window,
            width=160,
            height=60,
            bg="#1e1e1e",
            highlightthickness=0
        )
        self.canvas.pack()

        # 定位到屏幕右下角
        self.window.update_idletasks()
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = screen_w - 180
        y = screen_h - 100
        self.window.geometry(f"+{x}+{y}")

    def _animate_recording(self):
        if self.state != "recording":
            return
        for i in range(self._bar_count):
            self._bar_heights[i] = random.randint(8, 28)
        self._draw_bars()
        self._anim_job = self.root.after(80, self._animate_recording)

    def _animate_recognizing(self):
        if self.state != "recognizing":
            return
        self._arc_angle = (self._arc_angle + 12) % 360
        self._draw_arc()
        self._anim_job = self.root.after(40, self._animate_recognizing)

    def _draw_bars(self):
        if self.canvas is None:
            return
        self.canvas.delete("all")
        bar_w = 6
        gap = 8
        start_x = 20
        base_y = 40

        for i in range(self._bar_count):
            h = self._bar_heights[i]
            x0 = start_x + i * (bar_w + gap)
            y0 = base_y - h
            x1 = x0 + bar_w
            y1 = base_y
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#ff4757", outline="")

        self.canvas.create_text(
            100, 50,
            text="Recording",
            fill="#ffffff",
            font=("Microsoft YaHei", 9)
        )

    def _draw_arc(self):
        if self.canvas is None:
            return
        self.canvas.delete("all")
        cx, cy = 35, 25
        r = 14

        # 背景圆环
        self.canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=0, extent=360,
            outline="#3a3a3a", width=3, style="arc"
        )
        # 旋转圆弧
        self.canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=self._arc_angle, extent=60,
            outline="#3742fa", width=3, style="arc"
        )

        self.canvas.create_text(
            100, 28,
            text="Recognizing",
            fill="#ffffff",
            font=("Microsoft YaHei", 9)
        )

    def show_recording(self):
        root = self._get_root()
        if root is None:
            return
        root.after(0, self._show_recording_ui)

    def _show_recording_ui(self):
        self._stop_anim()
        self._create_window()
        self.window.deiconify()
        self.state = "recording"
        self._animate_recording()

    def show_recognizing(self):
        root = self._get_root()
        if root is None:
            return
        root.after(0, self._show_recognizing_ui)

    def _show_recognizing_ui(self):
        self._stop_anim()
        self._create_window()
        self.window.deiconify()
        self.state = "recognizing"
        self._animate_recognizing()

    def hide(self):
        root = self._get_root()
        if root is None:
            return
        root.after(0, self._hide_ui)

    def _hide_ui(self):
        self._stop_anim()
        self.state = "idle"
        if self.window is not None:
            self.window.withdraw()

    def _stop_anim(self):
        if self._anim_job is not None:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
