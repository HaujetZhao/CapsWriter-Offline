# coding: utf-8
"""
Linux 快捷键管理器

用 pynput 跨平台 API（on_press/on_release、on_click）替代
Windows 版的 win32_event_filter，实现相同的快捷键管理功能。

与 Windows 版 ShortcutManager 功能一致，但不支持 suppress（拦截按键）。
默认配置 suppress=False，通过录音结束后补发按键恢复状态。
"""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Dict, List, Optional

from pynput import keyboard, mouse

from . import logger
from .linux_key_mapper import LinuxKeyMapper as KeyMapper
from .linux_key_mapper import RESTORABLE_KEYS
from .emulator import ShortcutEmulator
from .event_handler import ShortcutEventHandler
from .task import ShortcutTask

if TYPE_CHECKING:
    from .shortcut_config import Shortcut
    from util.client.state import ClientState


class LinuxShortcutManager:
    """
    Linux 快捷键管理器

    功能与 Windows 版 ShortcutManager 对齐：
    - 多快捷键并发处理
    - 防止不同按键互相干扰
    - restore 功能（录音结束后恢复 CapsLock 状态）
    - hold_mode 和 click_mode 支持

    不支持 suppress（pynput 在 Linux 上无法拦截按键）。
    """

    def __init__(self, state: 'ClientState', shortcuts: List['Shortcut']):
        self.state = state
        self.shortcuts = shortcuts

        # 监听器
        self.keyboard_listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None

        # 快捷键任务映射（key_name -> ShortcutTask）
        self.tasks: Dict[str, ShortcutTask] = {}

        # 线程池
        self._pool = ThreadPoolExecutor(max_workers=4)

        # 按键模拟器
        self._emulator = ShortcutEmulator()

        # 按键恢复状态追踪
        self._restoring_keys = set()

        # 事件处理器
        self._event_handler = ShortcutEventHandler(self.tasks, self._pool, self._emulator)

        # 鼠标按键 → 任务 key 的映射
        # Linux 上 pynput 用 button8/button9 代替 Windows 的 x1/x2
        self._mouse_button_map = {
            mouse.Button.button8: 'x1',
            mouse.Button.button9: 'x2',
        }

        self._init_tasks()

    def _init_tasks(self) -> None:
        """初始化所有快捷键任务"""
        from config_client import ClientConfig as Config

        for shortcut in self.shortcuts:
            if not shortcut.enabled:
                continue

            task = ShortcutTask(shortcut, self.state)
            task._manager_ref = lambda: self
            task.pool = self._pool
            task.threshold = shortcut.get_threshold(Config.threshold)
            self.tasks[shortcut.key] = task

    # ========== 键盘回调 ==========

    def _on_press(self, key) -> None:
        """键盘按下回调"""
        key_name = KeyMapper.key_to_name(key)

        # 防自捕获：模拟按键补发时忽略
        if self._emulator.is_emulating(key_name):
            return
        # 防自捕获：恢复按键时忽略
        if key_name in self._restoring_keys:
            return

        if key_name not in self.tasks:
            return

        task = self.tasks[key_name]
        self._event_handler.handle_keydown(key_name, task)

    def _on_release(self, key) -> None:
        """键盘释放回调"""
        key_name = KeyMapper.key_to_name(key)

        # 模拟按键补发完成，清除标志
        if self._emulator.is_emulating(key_name):
            self._emulator.clear_emulating_flag(key_name)
            return
        # 恢复按键完成，清除标志
        if key_name in self._restoring_keys:
            self._restoring_keys.discard(key_name)
            return

        if key_name not in self.tasks:
            return

        task = self.tasks[key_name]

        # Linux 上 pynput 无法 suppress，系统已经处理了按键
        # 所以短按时不需要补发（补发会导致切换两次 = 没切换）
        if task.shortcut.hold_mode and task.is_recording:
            duration = time.time() - task.recording_start_time
            if duration < task.threshold:
                task.cancel()
                return

        self._event_handler.handle_keyup(key_name, task)

    # ========== 鼠标回调 ==========

    def _on_click(self, x, y, button, pressed) -> None:
        """鼠标按键回调"""
        button_name = self._mouse_button_map.get(button)
        if button_name is None:
            return

        # 防自捕获：模拟按键补发时忽略
        if self._emulator.is_emulating(button_name):
            if not pressed:
                self._emulator.clear_emulating_flag(button_name)
            return

        if button_name not in self.tasks:
            return

        task = self.tasks[button_name]

        if pressed:
            self._event_handler.handle_keydown(button_name, task)
        else:
            self._handle_mouse_keyup(button_name, task)

    def _handle_mouse_keyup(self, button_name: str, task) -> None:
        """处理鼠标按键释放事件"""
        # 单击模式
        if not task.shortcut.hold_mode:
            if task.pressed:
                task.pressed = False
                task.released = True
                task.event.set()
            return

        # 长按模式
        if not task.is_recording:
            return

        duration = time.time() - task.recording_start_time
        logger.debug(f"[{button_name}] 松开按键，持续时间: {duration:.3f}s")

        if duration < task.threshold:
            task.cancel()
            if task.shortcut.suppress:
                logger.debug(f"[{button_name}] 安排异步补发鼠标按键")
                self._pool.submit(self._emulator.emulate_mouse_click, button_name)
        else:
            task.finish()

    # ========== 按键恢复管理 ==========

    def schedule_restore(self, key: str) -> None:
        """
        安排按键恢复（延迟执行，避免在事件处理中阻塞）

        Args:
            key: 要恢复的按键
        """
        from pynput import keyboard

        self._restoring_keys.add(key)

        def do_restore():
            time.sleep(0.05)
            if key == 'caps_lock':
                controller = keyboard.Controller()
                controller.press(keyboard.Key.caps_lock)
                controller.release(keyboard.Key.caps_lock)

        self._pool.submit(do_restore)

    def is_restoring(self, key: str) -> bool:
        return key in self._restoring_keys

    def clear_restoring_flag(self, key: str) -> None:
        self._restoring_keys.discard(key)

    # ========== 公共接口 ==========

    def start(self) -> None:
        """启动所有监听器"""
        has_keyboard = any(s.type == 'keyboard' for s in self.shortcuts if s.enabled)
        has_mouse = any(s.type == 'mouse' for s in self.shortcuts if s.enabled)

        if has_keyboard:
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self.keyboard_listener.start()
            logger.info("键盘监听器已启动 (Linux)")

        if has_mouse:
            self.mouse_listener = mouse.Listener(
                on_click=self._on_click,
            )
            self.mouse_listener.start()
            logger.info("鼠标监听器已启动 (Linux)")

        for shortcut in self.shortcuts:
            if shortcut.enabled:
                mode = "长按" if shortcut.hold_mode else "单击"
                toggle = "可恢复" if any(t in shortcut.key for t in RESTORABLE_KEYS) else "普通键"
                logger.info(f"  [{shortcut.key}] {mode}模式, {toggle}")

    def stop(self) -> None:
        """停止所有监听器和清理资源"""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            logger.debug("键盘监听器已停止")

        if self.mouse_listener:
            self.mouse_listener.stop()
            logger.debug("鼠标监听器已停止")

        for task in self.tasks.values():
            if task.is_recording:
                task.cancel()

        self._pool.shutdown(wait=False)
        logger.debug("快捷键管理器线程池已关闭")
