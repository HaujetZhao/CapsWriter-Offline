# coding: utf-8
"""
按键映射相关

处理按键名称和虚拟键码之间的转换，以及相关常量定义
"""

import sys
from pynput import keyboard
from . import logger


IS_WINDOWS = sys.platform.startswith("win")


# =========================================================
# Windows KeyTranslator（仅 Windows）
# =========================================================

if IS_WINDOWS:
    from pynput._util.win32 import KeyTranslator
    _key_translator = KeyTranslator()
else:
    _key_translator = None


# =========================================================
# 特殊键 VK 映射
# =========================================================

_SPECIAL_KEYS = {
    key.value.vk: key
    for key in keyboard.Key
    if hasattr(key.value, "vk")
}


# =========================================================
# 小键盘映射
# =========================================================

NUMPAD_KEYS = {
    0x60: 'numpad0',  0x61: 'numpad1',  0x62: 'numpad2',  0x63: 'numpad3',
    0x64: 'numpad4',  0x65: 'numpad5',  0x66: 'numpad6',  0x67: 'numpad7',
    0x68: 'numpad8',  0x69: 'numpad9',
    0x6A: 'numpad_multiply',
    0x6B: 'numpad_add',
    0x6C: 'numpad_separator',
    0x6D: 'numpad_subtract',
    0x6E: 'numpad_decimal',
    0x6F: 'numpad_divide',
}


# =========================================================
# Windows 常量（Linux 不使用但保留）
# =========================================================

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C

XBUTTON1 = 0x0001
XBUTTON2 = 0x0002


KEYBOARD_MESSAGES = (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP)
KEY_UP_MESSAGES = (WM_KEYUP, WM_SYSKEYUP)
KEY_DOWN_MESSAGES = (WM_KEYDOWN, WM_SYSKEYDOWN)

MOUSE_MESSAGES = (WM_XBUTTONDOWN, WM_XBUTTONUP)


# =========================================================
# 可恢复锁键
# =========================================================

RESTORABLE_KEYS = {
    'caps_lock',
    'num_lock',
    'scroll_lock',
}


# =========================================================
# KeyMapper
# =========================================================

class KeyMapper:
    """按键映射器"""

    _SPECIAL_KEY_OBJECTS = None

    @classmethod
    def _get_special_key_objects(cls):
        """获取 pynput 特殊键对象"""

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

                'f1': keyboard.Key.f1,
                'f2': keyboard.Key.f2,
                'f3': keyboard.Key.f3,
                'f4': keyboard.Key.f4,
                'f5': keyboard.Key.f5,
                'f6': keyboard.Key.f6,
                'f7': keyboard.Key.f7,
                'f8': keyboard.Key.f8,
                'f9': keyboard.Key.f9,
                'f10': keyboard.Key.f10,
                'f11': keyboard.Key.f11,
                'f12': keyboard.Key.f12,
            }

        return cls._SPECIAL_KEY_OBJECTS

    # =========================================================
    # VK -> name
    # =========================================================

    @staticmethod
    def vk_to_name(vk: int) -> str:
        """
        虚拟键码 -> 名称
        """

        if vk in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[vk].name

        if vk in NUMPAD_KEYS:
            return NUMPAD_KEYS[vk]

        # Windows 使用 KeyTranslator
        if IS_WINDOWS and _key_translator:

            try:
                params = _key_translator(vk, is_press=True)

                if 'char' in params and params['char'] is not None:
                    return params['char']

            except Exception:
                pass

        # Linux/macOS fallback
        try:
            c = chr(vk)
            if c.isprintable():
                return c.lower()
        except Exception:
            pass

        return f'vk_{vk}'

    # =========================================================
    # name -> pynput key
    # =========================================================

    @staticmethod
    def name_to_key(key_name: str):

        special_keys = KeyMapper._get_special_key_objects()

        if key_name in special_keys:
            return special_keys[key_name]

        if len(key_name) == 1:
            return keyboard.KeyCode.from_char(key_name)

        logger.warning(f"未知按键名称: {key_name}")

        return None
