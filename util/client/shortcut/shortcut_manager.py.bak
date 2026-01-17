# coding: utf-8
"""
快捷键管理器

统一管理多个快捷键，处理键盘和鼠标事件，支持：
1. 多快捷键并发处理
2. 防止不同按键互相干扰
3. restore 功能的防自捕获逻辑
4. hold_mode 和 click_mode 支持
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Callable

from pynput import keyboard, mouse

from util.logger import get_logger
from util.tools.my_status import Status

if TYPE_CHECKING:
    from util.client.shortcut.shortcut_config import Shortcut
    from util.client.state import ClientState
    from util.client.audio.recorder import AudioRecorder

# Windows 键盘消息常量
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# 日志记录器
logger = get_logger('client')


class ShortcutTask:
    """
    单个快捷键的录音任务

    跟踪每个快捷键独立的录音状态，防止互相干扰。
    """

    def __init__(self, shortcut: Shortcut, state: 'ClientState', recorder_class=None):
        """
        初始化快捷键任务

        Args:
            shortcut: 快捷键配置
            state: 客户端状态实例
            recorder_class: AudioRecorder 类（可选，用于延迟导入）
        """
        self.shortcut = shortcut
        self.state = state
        self._recorder_class = recorder_class

        # 任务状态
        self.task: Optional[asyncio.Future] = None
        self.recording_start_time: float = 0.0
        self.is_recording: bool = False

        # hold_mode 状态跟踪
        self.pressed: bool = False
        self.released: bool = True
        self.event: Event = Event()

        # 线程池（用于 countdown）
        self.pool: Optional[ThreadPoolExecutor] = None

        # 录音状态动画
        self._status = Status('开始录音', spinner='point')

    def _get_recorder(self) -> 'AudioRecorder':
        """获取 AudioRecorder 实例"""
        if self._recorder_class is None:
            from util.client.audio.recorder import AudioRecorder
            self._recorder_class = AudioRecorder
        return self._recorder_class(self.state)

    def launch(self) -> None:
        """启动录音任务"""
        logger.info(f"[{self.shortcut.key}] 触发：开始录音")

        # 记录开始时间
        self.recording_start_time = time.time()
        self.is_recording = True

        # 将开始标志放入队列
        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({'type': 'begin', 'time': self.recording_start_time, 'data': None}),
            self.state.loop
        )

        # 更新录音状态
        self.state.start_recording(self.recording_start_time)

        # 打印动画：正在录音
        self._status.start()

        # 启动识别任务
        recorder = self._get_recorder()
        self.task = asyncio.run_coroutine_threadsafe(
            recorder.record_and_send(),
            self.state.loop,
        )

    def cancel(self) -> None:
        """取消录音任务（时间过短）"""
        logger.debug(f"[{self.shortcut.key}] 取消录音任务（时间过短）")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()

        if self.task:
            self.task.cancel()
            self.task = None

    def finish(self) -> None:
        """完成录音任务"""
        logger.info(f"[{self.shortcut.key}] 释放：完成录音")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()

        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({
                'type': 'finish',
                'time': time.time(),
                'data': None
            }),
            self.state.loop
        )

        # 执行 restore
        if self.shortcut.restore:
            self._restore_key()

    def _restore_key(self) -> None:
        """恢复按键状态（防自捕获逻辑由 ShortcutManager 处理）"""
        if not self.shortcut.is_toggle_key():
            return

        # 通知管理器执行 restore
        # 防自捕获：管理器会设置 flag 再发送按键
        from util.client.shortcut.shortcut_manager import ShortcutManager
        if hasattr(self, '_manager_ref'):
            manager = self._manager_ref()
            if manager:
                manager._schedule_restore(self.shortcut.key)


class ShortcutManager:
    """
    快捷键管理器

    统一管理多个快捷键，使用 pynput 监听键盘和鼠标事件。
    所有事件处理都在 win32_event_filter 中完成，确保高性能和低延迟。
    """

    def __init__(self, state: 'ClientState', shortcuts: List['Shortcut']):
        """
        初始化快捷键管理器

        Args:
            state: 客户端状态实例
            shortcuts: 快捷键配置列表
        """
        self.state = state
        self.shortcuts = shortcuts

        # 监听器
        self.keyboard_listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None

        # 快捷键任务映射（key -> ShortcutTask）
        self.tasks: Dict[str, ShortcutTask] = {}

        # restore 防自捕获标志
        self._restoring_keys: Set[str] = set()

        # emulate 防自捕获标志（短按补发按键）
        self._emulating_keys: Set[str] = set()

        # 线程池
        self._pool = ThreadPoolExecutor(max_workers=4)

        # 常驻 controller（用于异步补发按键，避免重复创建）
        self._keyboard_controller = keyboard.Controller()
        self._mouse_controller = mouse.Controller()

        # 初始化快捷键任务
        self._init_tasks()

    def _init_tasks(self) -> None:
        """初始化所有快捷键任务"""
        from config import ClientConfig as Config

        for shortcut in self.shortcuts:
            if not shortcut.enabled:
                continue

            task = ShortcutTask(shortcut, self.state)
            task._manager_ref = lambda: self  # 弱引用，用于回调
            task.pool = self._pool
            # 使用统一的阈值（或快捷键特定的阈值）
            task.threshold = shortcut.get_threshold(Config.threshold)
            self.tasks[shortcut.key] = task

    def _schedule_restore(self, key: str) -> None:
        """
        安排按键恢复（延迟执行，避免在事件处理中阻塞）

        Args:
            key: 要恢复的按键
        """
        # 设置防自捕获标志
        self._restoring_keys.add(key)

        # 延迟发送按键，确保当前事件处理完成
        def do_restore():
            time.sleep(0.01)
            try:
                if key == 'caps_lock':
                    keyboard.Controller().press(keyboard.Key.caps_lock)
                    keyboard.Controller().release(keyboard.Key.caps_lock)
                else:
                    # 其他按键的 restore 逻辑
                    pass
            finally:
                # 清除标志（无论是否成功）
                self._restoring_keys.discard(key)

        self._pool.submit(do_restore)

    def _is_restoring(self, key: str) -> bool:
        """
        检查是否正在恢复指定按键

        Args:
            key: 按键名称

        Returns:
            bool: 是否正在恢复
        """
        return key in self._restoring_keys

    # ========== 键盘事件处理 ==========

    def _create_keyboard_filter(self):
        """
        创建键盘事件过滤器（兼容 pynput win32_event_filter 格式）

        Returns:
            callable: 事件过滤函数
        """
        def win32_event_filter(msg, data):
            """
            键盘事件过滤器

            Args:
                msg: Windows 消息类型
                data: KBDLLHOOKSTRUCT 数据

            Returns:
                bool: True=继续传递事件，需要在 listener 上调用 suppress_event() 来阻塞
            """
            # 只处理 KEYDOWN 和 KEYUP 消息
            if msg not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                return True

            # 获取虚拟键码
            vk = data.vkCode

            # 将虚拟键码转换为按键名称
            key_name = self._vk_to_name(vk)

            # 防自捕获：检查是否正在模拟按键
            if key_name in self._emulating_keys:
                if msg in (WM_KEYUP, WM_SYSKEYUP):
                    self._emulating_keys.discard(key_name)  # 松开时清除标志
                return True  # 放行（按下时不清除标志）

            # 防自捕获：检查是否正在恢复按键
            if self._is_restoring(key_name):
                if msg in (WM_KEYUP, WM_SYSKEYUP):
                    self._restoring_keys.discard(key_name)
                return True

            # 查找匹配的快捷键
            if key_name not in self.tasks:
                return True

            task = self.tasks[key_name]
            shortcut = task.shortcut

            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                # 按下事件
                if shortcut.hold_mode:
                    # 长按模式：按下立即开始录音
                    if not task.is_recording:
                        task.launch()
                else:
                    # 单击模式
                    if task.released:
                        task.pressed = True
                        task.released = False
                        task.event = Event()
                        self._pool.submit(self._count_down, task)
                        self._pool.submit(self._manage_task, task)

            elif msg in (WM_KEYUP, WM_SYSKEYUP):
                # 释放事件
                if shortcut.hold_mode:
                    # 长按模式
                    if task.is_recording:
                        duration = time.time() - task.recording_start_time
                        logger.debug(f"[{key_name}] 松开，持续时间: {duration:.2f}s")

                        if duration < task.threshold:
                            task.cancel()
                            # 短按且 suppress=True：异步补发按键
                            if shortcut.suppress:
                                logger.debug(f"[{key_name}] 安排异步补发按键")
                                self._pool.submit(self._async_emulate_key, key_name)
                        else:
                            task.finish()
                else:
                    # 单击模式
                    if task.pressed:
                        task.pressed = False
                        task.released = True
                        task.event.set()

            # 如果需要阻塞事件，在这里调用 suppress_event()
            if shortcut.suppress and self.keyboard_listener:
                self.keyboard_listener.suppress_event()

            return True

        return win32_event_filter

    def _count_down(self, task: ShortcutTask) -> None:
        """倒计时（单击模式）"""
        time.sleep(task.threshold)
        task.event.set()

    def _manage_task(self, task: ShortcutTask) -> None:
        """管理录音任务（单击模式）"""
        was_recording = task.is_recording

        if not was_recording:
            task.launch()

        if task.event.wait(timeout=task.threshold * 0.8):
            if task.is_recording and was_recording:
                task.finish()
        else:
            if not was_recording:
                task.cancel()

    # ========== 鼠标事件处理 ==========

    def _create_mouse_filter(self):
        """
        创建鼠标事件过滤器（兼容 pynput win32_event_filter 格式）

        Returns:
            callable: 事件过滤函数
        """
        # Windows 鼠标消息常量
        WM_XBUTTONDOWN = 0x020B
        WM_XBUTTONUP = 0x020C
        XBUTTON1 = 0x0001
        XBUTTON2 = 0x0002

        def win32_event_filter(msg, data):
            """
            鼠标事件过滤器

            Args:
                msg: Windows 消息类型
                data: MSLLHOOKSTRUCT 数据

            Returns:
                bool: True=继续传递事件，需要在 listener 上调用 suppress_event() 来阻塞
            """
            # 只处理 XBUTTON 消息
            if msg not in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                return True

            # 获取按键标识
            xbutton = (data.mouseData >> 16) & 0xFFFF
            button_name = 'x1' if xbutton == XBUTTON1 else 'x2'

            # 防自捕获：检查是否正在模拟鼠标按键
            if button_name in self._emulating_keys:
                if msg == WM_XBUTTONUP:
                    self._emulating_keys.discard(button_name)  # 松开时清除标志
                return True  # 放行（按下时不清除标志）

            # 查找匹配的快捷键
            if button_name not in self.tasks:
                return True

            task = self.tasks[button_name]
            shortcut = task.shortcut

            if msg == WM_XBUTTONDOWN:
                # 按下
                if shortcut.hold_mode:
                    if not task.is_recording:
                        task.launch()
                else:
                    if task.released:
                        task.pressed = True
                        task.released = False
                        task.event = Event()
                        self._pool.submit(self._count_down, task)
                        self._pool.submit(self._manage_task, task)

            elif msg == WM_XBUTTONUP:
                # 释放
                if shortcut.hold_mode:
                    if task.is_recording:
                        duration = time.time() - task.recording_start_time
                        logger.debug(f"[{button_name}] 松开按键，持续时间: {duration:.3f}s")
                        if duration < task.threshold:
                            cancel_start = time.perf_counter()
                            task.cancel()
                            cancel_time = (time.perf_counter() - cancel_start) * 1000
                            logger.debug(f"[{button_name}] task.cancel() 耗时: {cancel_time:.2f}ms")

                            # 短按且 suppress=True：异步补发鼠标按键
                            if shortcut.suppress:
                                logger.debug(f"[{button_name}] 安排异步补发鼠标按键")
                                self._pool.submit(self._async_emulate_mouse_click, button_name)
                        else:
                            task.finish()
                else:
                    if task.pressed:
                        task.pressed = False
                        task.released = True
                        task.event.set()

                # restore 逻辑在 task.finish() 中处理

            # 如果需要阻塞事件，在这里调用 suppress_event()
            if shortcut.suppress and self.mouse_listener:
                self.mouse_listener.suppress_event()

            return True

        return win32_event_filter

    # ========== 辅助方法 ==========

    def _async_emulate_key(self, key_name: str) -> None:
        """
        异步补发按键（在线程池中调用）

        Args:
            key_name: 按键名称（如 'caps_lock', 'f12'）
        """
        try:
            self._emulating_keys.add(key_name)

            key_obj = self._name_to_key(key_name)
            if key_obj is not None:
                self._keyboard_controller.press(key_obj)
                self._keyboard_controller.release(key_obj)
                logger.debug(f"[{key_name}] 补发按键成功")
            else:
                logger.warning(f"[{key_name}] 无法识别的按键，跳过补发")
        except Exception as e:
            logger.error(f"[{key_name}] 补发按键失败: {e}")

    def _async_emulate_mouse_click(self, button_name: str) -> None:
        """
        异步补发鼠标按键（在线程池中调用）

        Args:
            button_name: 鼠标按键名称（'x1' 或 'x2'）
        """
        try:
            self._emulating_keys.add(button_name)

            # pynput 鼠标按键对象映射
            button_map = {
                'x1': mouse.Button.x1,
                'x2': mouse.Button.x2
            }

            if button_name in button_map:
                button = button_map[button_name]
                self._mouse_controller.press(button)
                self._mouse_controller.release(button)
                logger.debug(f"[{button_name}] 补发鼠标按键成功")
            else:
                logger.warning(f"[{button_name}] 无法识别的鼠标按键，跳过补发")
        except Exception as e:
            logger.error(f"[{button_name}] 补发鼠标按键失败: {e}")

    @staticmethod
    def _name_to_key(key_name: str):
        """
        将按键名称转换为 pynput 按键对象

        Args:
            key_name: 按键名称

        Returns:
            pynput 按键对象或 None
        """
        # 特殊按键映射
        special_keys = {
            'caps_lock': keyboard.Key.caps_lock,
            'space': keyboard.Key.space,
            'tab': keyboard.Key.tab,
            'enter': keyboard.Key.enter,
            'esc': keyboard.Key.esc,
            'delete': keyboard.Key.delete,
            'backspace': keyboard.Key.backspace,
            'shift': keyboard.Key.shift,
            'ctrl': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'cmd': keyboard.Key.cmd,
            'f1': keyboard.Key.f1, 'f2': keyboard.Key.f2, 'f3': keyboard.Key.f3, 'f4': keyboard.Key.f4,
            'f5': keyboard.Key.f5, 'f6': keyboard.Key.f6, 'f7': keyboard.Key.f7, 'f8': keyboard.Key.f8,
            'f9': keyboard.Key.f9, 'f10': keyboard.Key.f10, 'f11': keyboard.Key.f11, 'f12': keyboard.Key.f12,
        }

        if key_name in special_keys:
            return special_keys[key_name]

        # 单个字符按键
        if len(key_name) == 1:
            return keyboard.KeyCode.from_char(key_name)

        logger.warning(f"未知按键名称: {key_name}")
        return None

    @staticmethod
    def _vk_to_name(vk: int) -> str:
        """
        将虚拟键码转换为按键名称

        Args:
            vk: 虚拟键码

        Returns:
            str: 按键名称（与 Shortcut.key 格式一致）
        """
        # 常用虚拟键码映射
        vk_map = {
            0x14: 'caps_lock',
            0x20: 'space',
            0x09: 'tab',
            0x0D: 'enter',
            0x1B: 'esc',
            0x2E: 'delete',
            0x08: 'backspace',

            # F1-F12
            0x70: 'f1', 0x71: 'f2', 0x72: 'f3', 0x73: 'f4',
            0x74: 'f5', 0x75: 'f6', 0x76: 'f7', 0x77: 'f8',
            0x78: 'f9', 0x79: 'f10', 0x7A: 'f11', 0x7B: 'f12',

            # 字母 A-Z
            **{0x41 + i: chr(0x41 + i).lower() for i in range(26)},

            # 数字 0-9
            **{0x30 + i: str(i) for i in range(10)},
        }

        # 首先查表
        if vk in vk_map:
            return vk_map[vk]

        # 尝试转换为字符
        if 0x30 <= vk <= 0x39:  # 0-9
            return str(vk - 0x30)
        if 0x41 <= vk <= 0x5A:  # A-Z
            return chr(vk).lower()

        # 未知键码，返回 vk_ 格式
        return f'vk_{vk}'

    # ========== 公共接口 ==========

    def start(self) -> None:
        """启动所有监听器"""
        # 检查是否有键盘快捷键
        has_keyboard = any(s.type == 'keyboard' for s in self.shortcuts if s.enabled)
        has_mouse = any(s.type == 'mouse' for s in self.shortcuts if s.enabled)

        if has_keyboard:
            try:
                self.keyboard_listener = keyboard.Listener(
                    win32_event_filter=self._create_keyboard_filter()
                )
                self.keyboard_listener.start()
                logger.info("键盘监听器已启动")
            except Exception as e:
                logger.error(f"启动键盘监听器失败: {e}")

        if has_mouse:
            try:
                self.mouse_listener = mouse.Listener(
                    win32_event_filter=self._create_mouse_filter()
                )
                self.mouse_listener.start()
                logger.info("鼠标监听器已启动")
            except Exception as e:
                logger.error(f"启动鼠标监听器失败: {e}")

        # 打印所有启用的快捷键
        for shortcut in self.shortcuts:
            if shortcut.enabled:
                mode = "长按" if shortcut.hold_mode else "单击"
                logger.info(f"  [{shortcut.key}] {mode}模式, 阻塞:{shortcut.suppress}, restore:{shortcut.restore}")

    def stop(self) -> None:
        """停止所有监听器和清理资源"""
        if self.keyboard_listener and self.keyboard_listener.running:
            self.keyboard_listener.stop()
            logger.debug("键盘监听器已停止")

        if self.mouse_listener and self.mouse_listener.running:
            self.mouse_listener.stop()
            logger.debug("鼠标监听器已停止")

        # 取消所有任务
        for task in self.tasks.values():
            if task.is_recording:
                task.cancel()

        # 关闭线程池
        if self._pool:
            self._pool.shutdown(wait=False)
            logger.debug("快捷键管理器线程池已关闭")
