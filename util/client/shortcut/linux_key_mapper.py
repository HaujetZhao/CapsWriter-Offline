# coding: utf-8
"""
Linux 按键映射模块

将 pynput 在 Linux 上的按键对象转换为统一键名，
以及将统一键名转换回 pynput 按键对象。

与 Windows 版 key_mapper.py 不同，pynput 在 Linux 上
直接提供 Key 枚举或 KeyCode(char)，无需 X11 keycode 中转。
"""

from pynput import keyboard

from . import logger


# 可恢复的切换键（录音完成后需要恢复状态的锁键）
RESTORABLE_KEYS = {
    'caps_lock',    # 大写锁定
    'num_lock',     # 数字键盘锁定
    'scroll_lock',  # 滚动锁定
}


class LinuxKeyMapper:
    """Linux 按键映射器"""

    # pynput 特殊键对象缓存
    _SPECIAL_KEY_OBJECTS = None

    @classmethod
    def _get_special_key_objects(cls):
        """获取 pynput 特殊键对象（延迟初始化）"""
        if cls._SPECIAL_KEY_OBJECTS is None:
            cls._SPECIAL_KEY_OBJECTS = {
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
        return cls._SPECIAL_KEY_OBJECTS

    @staticmethod
    def key_to_name(key) -> str:
        """
        将 pynput 按键对象转换为统一键名

        Args:
            key: pynput.keyboard.Key 枚举 或 KeyCode 对象

        Returns:
            str: 统一键名（与 Shortcut.key 格式一致）

        Examples:
            Key.caps_lock → 'caps_lock'
            KeyCode(char='a') → 'a'
            KeyCode(char='A') → 'a'
            KeyCode(vk=65) → 'a'
        """
        # pynput Key 枚举（特殊键）
        if isinstance(key, keyboard.Key):
            return key.name

        # KeyCode（字母、数字、符号键）
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.lower()
            if key.vk is not None:
                # ASCII 范围内的虚拟键码
                if 0x41 <= key.vk <= 0x5A:  # A-Z
                    return chr(key.vk).lower()
                if 0x30 <= key.vk <= 0x39:  # 0-9
                    return chr(key.vk)

        # 无法识别
        logger.warning(f"未知的按键对象: {key}")
        return str(key)

    @staticmethod
    def name_to_key(key_name: str):
        """
        将按键名称转换为 pynput 按键对象

        Args:
            key_name: 按键名称

        Returns:
            pynput 按键对象或 None
        """
        # 特殊按键
        special_keys = LinuxKeyMapper._get_special_key_objects()
        if key_name in special_keys:
            return special_keys[key_name]

        # 单个字符按键
        if len(key_name) == 1:
            return keyboard.KeyCode.from_char(key_name)

        logger.warning(f"未知按键名称: {key_name}")
        return None
