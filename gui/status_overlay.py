"""
状态悬浮窗 - 显示录音/识别状态的浮动窗口
支持音量波纹可视化
"""

import tkinter as tk
from tkinter import Canvas
from typing import Optional, List
import time
import math
import random


class StatusOverlay(tk.Toplevel):
    """状态悬浮窗 - 无边框透明置顶窗口，带音量波纹"""
    
    # 状态图标
    STATUS_ICONS = {
        'idle': '',
        'recording': '🎙️',
        'processing': '⏳',
        'done': '✅',
        'error': '❌'
    }
    
    # 状态文本
    STATUS_TEXT = {
        'idle': '',
        'recording': '正在录音',
        'processing': '正在识别',
        'done': '完成',
        'error': '出错'
    }
    
    # 位置预设：只保留底部三个位置
    POSITIONS = {
        'bottom_left': (0.05, 0.92),
        'bottom_center': (0.5, 0.92),
        'bottom_right': (0.95, 0.92)
    }
    
    # 波纹配置
    WAVE_BARS = 9          # 波纹条数（增加）
    WAVE_BAR_WIDTH = 4     # 每条宽度
    WAVE_BAR_GAP = 3       # 条间距
    WAVE_MAX_HEIGHT = 28   # 最大高度
    WAVE_MIN_HEIGHT = 5    # 最小高度
    WAVE_COLOR = '#4CAF50' # 波纹颜色（录音时）
    WAVE_COLOR_PROCESSING = '#FFC107'  # 处理时颜色
    
    def __init__(
        self,
        position: str = 'bottom_center',
        opacity: float = 0.9,
        auto_hide_delay: float = 1.5
    ):
        """
        初始化悬浮窗
        
        Args:
            position: 位置预设 ('bottom_left', 'bottom_center', 'bottom_right')
            opacity: 透明度 (0.3-1.0)
            auto_hide_delay: 自动隐藏延迟（秒）
        """
        super().__init__()
        
        self.position_key = position if position in self.POSITIONS else 'bottom_center'
        self.opacity = max(0.3, min(1.0, opacity))
        self.auto_hide_delay = auto_hide_delay
        
        # 状态
        self.current_status = 'idle'
        self.recording_start_time: Optional[float] = None
        self.hide_timer: Optional[str] = None
        self.wave_update_id: Optional[str] = None
        
        # 音量数据
        self.current_volume = 0.0  # 0.0 - 1.0
        self.wave_heights: List[float] = [0.3] * self.WAVE_BARS
        
        # 窗口设置
        self._setup_window()
        self._create_ui()
        self._position_window()
        
        # 初始隐藏
        self.withdraw()
    
    def _setup_window(self):
        """配置窗口属性"""
        # 无边框
        self.overrideredirect(True)
        
        # 置顶
        self.attributes('-topmost', True)
        
        # 透明度
        self.attributes('-alpha', self.opacity)
        
        # 背景色
        self.configure(bg='#1a1a2e')
    
    def _create_ui(self):
        """创建界面 - 简洁版：波形 + 状态文字"""
        # 主容器 - 使用 pack 垂直居中
        self.container = tk.Frame(
            self,
            bg='#1a1a2e',
            padx=14,
            pady=10
        )
        self.container.pack(fill='both', expand=True)
        
        # 左侧：波纹区域（垂直居中）
        wave_width = self.WAVE_BARS * (self.WAVE_BAR_WIDTH + self.WAVE_BAR_GAP)
        self.wave_canvas = Canvas(
            self.container,
            width=wave_width,
            height=self.WAVE_MAX_HEIGHT,
            bg='#1a1a2e',
            highlightthickness=0
        )
        self.wave_canvas.pack(side='left', padx=(0, 12), anchor='center')
        
        # 初始化波纹条
        self._init_wave_bars()
        
        # 右侧：状态文本（垂直居中，只有一行）
        self.status_label = tk.Label(
            self.container,
            text='正在录音',
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='#1a1a2e',
            fg='white',
            anchor='w'
        )
        self.status_label.pack(side='left', anchor='center')
    
    def _init_wave_bars(self):
        """初始化波纹条"""
        self.wave_bar_ids = []
        for i in range(self.WAVE_BARS):
            x = i * (self.WAVE_BAR_WIDTH + self.WAVE_BAR_GAP) + self.WAVE_BAR_WIDTH // 2
            # 创建圆角矩形（用线条模拟）
            bar_id = self.wave_canvas.create_rectangle(
                x, self.WAVE_MAX_HEIGHT,
                x + self.WAVE_BAR_WIDTH, self.WAVE_MAX_HEIGHT - self.WAVE_MIN_HEIGHT,
                fill=self.WAVE_COLOR,
                outline='',
                width=0
            )
            self.wave_bar_ids.append(bar_id)
    
    def _position_window(self):
        """定位窗口"""
        self.update_idletasks()
        
        # 获取屏幕尺寸
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # 获取窗口尺寸
        window_width = self.winfo_reqwidth()
        window_height = self.winfo_reqheight()
        
        # 获取位置比例
        x_ratio, y_ratio = self.POSITIONS.get(self.position_key, (0.5, 0.92))
        
        # 计算位置
        x = int(screen_width * x_ratio - window_width * x_ratio)
        y = int(screen_height * y_ratio - window_height)
        
        # 确保不超出屏幕，底部留 20px 边距
        x = max(20, min(x, screen_width - window_width - 20))
        y = min(y, screen_height - window_height - 40)
        
        self.geometry(f'+{x}+{y}')
    
    def show(self, status: str = 'recording', role: str = None):
        """
        显示悬浮窗
        
        Args:
            status: 状态 ('recording', 'processing', 'done', 'error')
            role: 角色名称（可选，显示在状态文字中）
        """
        # 取消之前的隐藏计时器
        if self.hide_timer:
            self.after_cancel(self.hide_timer)
            self.hide_timer = None
        
        # 更新状态
        self.current_status = status
        
        # 更新状态文本
        text = self.STATUS_TEXT.get(status, '')
        if role and status == 'recording':
            text = f'{text} - {role}'
        self.status_label.configure(text=text)
        
        # 更新波纹颜色
        wave_color = self.WAVE_COLOR if status == 'recording' else self.WAVE_COLOR_PROCESSING
        for bar_id in self.wave_bar_ids:
            self.wave_canvas.itemconfig(bar_id, fill=wave_color)
        
        # 启动对应动画
        if status == 'recording':
            self._start_wave_animation()
        elif status == 'processing':
            self._start_processing_wave()
            # 15秒超时保护：防止服务端无响应时悬浮窗一直显示
            self.hide_timer = self.after(15000, self._do_hide)
        elif status in ('done', 'error'):
            self._stop_wave_animation()
            self._reset_wave_bars()
            self._schedule_hide()
        
        # 显示窗口
        self.deiconify()
        self.lift()
    
    def hide(self, delay_ms: int = 0):
        """
        隐藏悬浮窗
        
        Args:
            delay_ms: 延迟隐藏的毫秒数
        """
        if delay_ms > 0:
            self.hide_timer = self.after(delay_ms, self._do_hide)
        else:
            self._do_hide()
    
    def _do_hide(self):
        """执行隐藏"""
        self._stop_wave_animation()
        self.withdraw()
        self.current_status = 'idle'
        self.current_volume = 0.0
    
    def _schedule_hide(self):
        """安排自动隐藏"""
        delay_ms = int(self.auto_hide_delay * 1000)
        self.hide_timer = self.after(delay_ms, self._do_hide)
    
    def _stop_all_animations(self):
        """停止所有动画"""
        self._stop_wave_animation()
    
    # ========== 波纹动画 ==========
    
    def set_volume(self, volume: float):
        """
        设置当前音量（外部调用）
        
        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        self.current_volume = max(0.0, min(1.0, volume))
    
    def _start_wave_animation(self):
        """开始波纹动画"""
        self._animate_wave()
    
    def _stop_wave_animation(self):
        """停止波纹动画"""
        if self.wave_update_id:
            self.after_cancel(self.wave_update_id)
            self.wave_update_id = None
    
    def _animate_wave(self):
        """波纹动画帧"""
        if self.current_status != 'recording':
            return
        
        # 基于音量计算目标高度
        base_height = self.WAVE_MIN_HEIGHT / self.WAVE_MAX_HEIGHT
        volume_contribution = self.current_volume * 0.7
        
        for i in range(self.WAVE_BARS):
            # 每个条有不同的随机性，模拟自然波动
            random_factor = random.uniform(0.7, 1.0)
            target = base_height + volume_contribution * random_factor
            
            # 平滑过渡
            current = self.wave_heights[i]
            self.wave_heights[i] = current + (target - current) * 0.3
            
            # 更新显示
            height = int(self.wave_heights[i] * self.WAVE_MAX_HEIGHT)
            height = max(self.WAVE_MIN_HEIGHT, min(self.WAVE_MAX_HEIGHT, height))
            
            x = i * (self.WAVE_BAR_WIDTH + self.WAVE_BAR_GAP)
            self.wave_canvas.coords(
                self.wave_bar_ids[i],
                x, self.WAVE_MAX_HEIGHT - height,
                x + self.WAVE_BAR_WIDTH, self.WAVE_MAX_HEIGHT
            )
        
        # 60fps
        self.wave_update_id = self.after(16, self._animate_wave)
    
    def _start_processing_wave(self):
        """处理时的波纹动画（缓慢呼吸效果）"""
        self._animate_processing_wave(0)
    
    def _animate_processing_wave(self, phase: int):
        """处理状态波纹动画"""
        if self.current_status != 'processing':
            return
        
        # 呼吸效果
        for i in range(self.WAVE_BARS):
            # 波浪相位偏移
            offset = (phase + i * 15) % 100
            height_ratio = 0.3 + 0.3 * math.sin(offset * math.pi / 50)
            
            height = int(height_ratio * self.WAVE_MAX_HEIGHT)
            height = max(self.WAVE_MIN_HEIGHT, height)
            
            x = i * (self.WAVE_BAR_WIDTH + self.WAVE_BAR_GAP)
            self.wave_canvas.coords(
                self.wave_bar_ids[i],
                x, self.WAVE_MAX_HEIGHT - height,
                x + self.WAVE_BAR_WIDTH, self.WAVE_MAX_HEIGHT
            )
        
        self.wave_update_id = self.after(50, lambda: self._animate_processing_wave(phase + 1))
    
    def _reset_wave_bars(self):
        """重置波纹条到最小高度"""
        for i, bar_id in enumerate(self.wave_bar_ids):
            x = i * (self.WAVE_BAR_WIDTH + self.WAVE_BAR_GAP)
            self.wave_canvas.coords(
                bar_id,
                x, self.WAVE_MAX_HEIGHT - self.WAVE_MIN_HEIGHT,
                x + self.WAVE_BAR_WIDTH, self.WAVE_MAX_HEIGHT
            )
        self.wave_heights = [self.WAVE_MIN_HEIGHT / self.WAVE_MAX_HEIGHT] * self.WAVE_BARS
    
    def update_config(self, position: str = None, opacity: float = None, auto_hide_delay: float = None):
        """
        更新配置
        
        Args:
            position: 新位置
            opacity: 新透明度
            auto_hide_delay: 新的自动隐藏延迟
        """
        if position is not None and position in self.POSITIONS:
            self.position_key = position
            self._position_window()
        
        if opacity is not None:
            self.opacity = max(0.3, min(1.0, opacity))
            self.attributes('-alpha', self.opacity)
        
        if auto_hide_delay is not None:
            self.auto_hide_delay = auto_hide_delay


# 全局悬浮窗实例
_overlay_instance: Optional[StatusOverlay] = None


def get_overlay() -> StatusOverlay:
    """获取全局悬浮窗实例"""
    global _overlay_instance
    if _overlay_instance is None:
        # 需要有 Tk 根窗口
        try:
            root = tk._default_root
            if root is None:
                root = tk.Tk()
                root.withdraw()
        except:
            root = tk.Tk()
            root.withdraw()
        
        _overlay_instance = StatusOverlay()
    
    return _overlay_instance


def show_status(status: str, role: str = None):
    """显示状态（便捷函数）"""
    overlay = get_overlay()
    overlay.show(status, role)


def hide_status(delay_ms: int = 0):
    """隐藏状态（便捷函数）"""
    overlay = get_overlay()
    overlay.hide(delay_ms)


def set_volume(volume: float):
    """设置音量（便捷函数）"""
    overlay = get_overlay()
    overlay.set_volume(volume)
