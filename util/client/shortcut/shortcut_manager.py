# coding: utf-8
"""
快捷键管理器（重构版）

统一管理多个快捷键，处理键盘和鼠标事件，支持：
1. 多快捷键并发处理
2. 防止不同按键互相干扰
3. restore 功能的防自捕获逻辑
4. hold_mode 和 click_mode 支持
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Dict, List, Optional

from pynput import keyboard, mouse

from . import logger
from util.client.shortcut.key_mapper import *
from util.client.shortcut.key_mapper import KeyMapper
from util.client.shortcut.emulator import ShortcutEmulator
from util.client.shortcut.event_handler import ShortcutEventHandler
from util.client.shortcut.task import ShortcutTask

if TYPE_CHECKING:
    from util.client.shortcut.shortcut_config import Shortcut
    from util.client.state import ClientState


IS_WINDOWS = sys.platform.startswith("win")


class ShortcutManager:
    """
    快捷键管理器
    """

    def __init__(self, state: 'ClientState', shortcuts: List['Shortcut']):
        self.state = state
        self.shortcuts = shortcuts

        self.keyboard_listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None

        self.tasks: Dict[str, ShortcutTask] = {}

        self._pool = ThreadPoolExecutor(max_workers=4)

        self._emulator = ShortcutEmulator()

        self._restoring_keys = set()

        self._event_handler = ShortcutEventHandler(
            self.tasks,
            self._pool,
            self._emulator
        )

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

    # =========================================================
    # Windows 事件过滤器
    # =========================================================

    def create_keyboard_filter(self):
        """创建键盘事件过滤器 (Windows only)"""

        def win32_event_filter(msg, data):

            if msg not in KEYBOARD_MESSAGES:
                return True

            key_name = KeyMapper.vk_to_name(data.vkCode)

            if self._check_emulating(key_name, msg):
                return True

            if self._check_restoring(key_name, msg):
                return True

            if key_name not in self.tasks:
                return True

            task = self.tasks[key_name]

            if msg in KEY_DOWN_MESSAGES:
                self._event_handler.handle_keydown(key_name, task)

            elif msg in KEY_UP_MESSAGES:
                self._event_handler.handle_keyup(key_name, task)

            if task.shortcut.suppress and self.keyboard_listener:
                self.keyboard_listener.suppress_event()

            return True

        return win32_event_filter

    def create_mouse_filter(self):
        """创建鼠标事件过滤器 (Windows only)"""

        def win32_event_filter(msg, data):

            if msg not in MOUSE_MESSAGES:
                return True

            xbutton = (data.mouseData >> 16) & 0xFFFF
            button_name = 'x1' if xbutton == XBUTTON1 else 'x2'

            if self._check_emulating(button_name, msg, is_mouse=True):
                return True

            if button_name not in self.tasks:
                return True

            task = self.tasks[button_name]

            if msg == WM_XBUTTONDOWN:
                self._event_handler.handle_keydown(button_name, task)

            elif msg == WM_XBUTTONUP:
                self._handle_mouse_keyup(button_name, task)

            if task.shortcut.suppress and self.mouse_listener:
                self.mouse_listener.suppress_event()

            return True

        return win32_event_filter

    # =========================================================
    # Linux / macOS 适配
    # =========================================================

    def _key_to_name(self, key):

        try:
            return key.char
        except AttributeError:
            return str(key).replace("Key.", "").lower()

    def _mouse_to_name(self, button):

        name = str(button).lower()

        if "x1" in name:
            return "x1"

        if "x2" in name:
            return "x2"

        return name.replace("button.", "")

    def _on_press(self, key):

        key_name = self._key_to_name(key)

        if key_name not in self.tasks:
            return

        task = self.tasks[key_name]

        self._event_handler.handle_keydown(key_name, task)

    def _on_release(self, key):

        key_name = self._key_to_name(key)

        if key_name not in self.tasks:
            return

        task = self.tasks[key_name]

        self._event_handler.handle_keyup(key_name, task)

    def _on_click(self, x, y, button, pressed):

        button_name = self._mouse_to_name(button)

        if button_name not in self.tasks:
            return

        task = self.tasks[button_name]

        if pressed:
            self._event_handler.handle_keydown(button_name, task)
        else:
            self._handle_mouse_keyup(button_name, task)

    # =========================================================
    # 鼠标 KeyUp 处理
    # =========================================================

    def _handle_mouse_keyup(self, button_name: str, task) -> None:

        if not task.shortcut.hold_mode:

            if task.pressed:
                task.pressed = False
                task.released = True
                task.event.set()

            return

        if not task.is_recording:
            return

        duration = time.time() - task.recording_start_time

        logger.debug(f"[{button_name}] 松开按键，持续时间: {duration:.3f}s")

        if duration < task.threshold:

            task.cancel()

            if task.shortcut.suppress:
                logger.debug(f"[{button_name}] 安排异步补发鼠标按键")

                self._pool.submit(
                    self._emulator.emulate_mouse_click,
                    button_name
                )

        else:

            task.finish()

    # =========================================================
    # Restore 管理
    # =========================================================

    def schedule_restore(self, key: str) -> None:

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

    # =========================================================
    # 防自捕获
    # =========================================================

    def _check_emulating(self, key_name: str, msg: int, is_mouse: bool = False) -> bool:

        if not self._emulator.is_emulating(key_name):
            return False

        if is_mouse:

            if msg == WM_XBUTTONUP:
                self._emulator.clear_emulating_flag(key_name)

        else:

            if msg in (WM_KEYUP, WM_SYSKEYUP):
                self._emulator.clear_emulating_flag(key_name)

        return True

    def _check_restoring(self, key_name: str, msg: int) -> bool:

        if not self.is_restoring(key_name):
            return False

        if msg in (WM_KEYUP, WM_SYSKEYUP):
            self.clear_restoring_flag(key_name)

        return True

    # =========================================================
    # 启动监听
    # =========================================================

    def start(self) -> None:

        has_keyboard = any(
            s.type == 'keyboard' for s in self.shortcuts if s.enabled
        )

        has_mouse = any(
            s.type == 'mouse' for s in self.shortcuts if s.enabled
        )

        if has_keyboard:

            if IS_WINDOWS:

                self.keyboard_listener = keyboard.Listener(
                    win32_event_filter=self.create_keyboard_filter()
                )

            else:

                self.keyboard_listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release
                )

            self.keyboard_listener.start()

            logger.info("键盘监听器已启动")

        if has_mouse:

            if IS_WINDOWS:

                self.mouse_listener = mouse.Listener(
                    win32_event_filter=self.create_mouse_filter()
                )

            else:

                self.mouse_listener = mouse.Listener(
                    on_click=self._on_click
                )

            self.mouse_listener.start()

            logger.info("鼠标监听器已启动")

        for shortcut in self.shortcuts:

            if shortcut.enabled:

                mode = "长按" if shortcut.hold_mode else "单击"

                toggle = "可恢复" if shortcut.is_toggle_key() else "普通键"

                logger.info(
                    f"  [{shortcut.key}] {mode}模式, 阻塞:{shortcut.suppress}, {toggle}"
                )

    # =========================================================
    # 停止
    # =========================================================

    def stop(self) -> None:

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
