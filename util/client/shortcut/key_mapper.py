# coding: utf-8
"""
按键映射相关

处理按键名称和虚拟键码之间的转换，以及相关常量定义
"""

from pynput import keyboard
from pynput._util.win32 import KeyTranslator
from . import logger


# 创建键盘翻译器实例（用于 VK 到字符的转换）
_key_translator = KeyTranslator()

# 特殊键 VK 映射（从 pynput 复制）
_SPECIAL_KEYS = {
    key.value.vk: key
    for key in keyboard.Key
}

# 小键盘按键映射（VK -> 名称）
NUMPAD_KEYS = {
    0x60: 'numpad0',  0x61: 'numpad1',  0x62: 'numpad2',  0x63: 'numpad3',
    0x64: 'numpad4',  0x65: 'numpad5',  0x66: 'numpad6',  0x67: 'numpad7',
    0x68: 'numpad8',  0x69: 'numpad9',
    0x6A: 'numpad_multiply',  # *
    0x6B: 'numpad_add',       # +
    0x6C: 'numpad_separator', # （通常未使用）
    0x6D: 'numpad_subtract',  # -
    0x6E: 'numpad_decimal',   # 小数点
    0x6F: 'numpad_divide',    # /
}

# Windows 键盘消息常量
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Windows 鼠标消息常量
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

# 按键消息集合
KEYBOARD_MESSAGES = (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP)
KEY_UP_MESSAGES = (WM_KEYUP, WM_SYSKEYUP)
KEY_DOWN_MESSAGES = (WM_KEYDOWN, WM_SYSKEYDOWN)
MOUSE_MESSAGES = (WM_XBUTTONDOWN, WM_XBUTTONUP)

# 可恢复的切换键（需要录音完成后恢复状态的锁键）
RESTORABLE_KEYS = {
    'caps_lock',    # 大写锁定
    'num_lock',     # 数字键盘锁定
    'scroll_lock',  # 滚动锁定
}


class KeyMapper:
    """按键映射器"""

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
    def vk_to_name(vk: int) -> str:
        """
        将虚拟键码转换为按键名称

        Args:
            vk: 虚拟键码

        Returns:
            str: 按键名称（与 Shortcut.key 格式一致）
        """
        # 首先检查是否是特殊键（pynput Key 枚举）
        if vk in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[vk].name

        # 检查是否是小键盘按键
        if vk in NUMPAD_KEYS:
            return NUMPAD_KEYS[vk]

        # 使用 pynput 的 KeyTranslator 获取字符（字母、数字、符号键）
        try:
            params = _key_translator(vk, is_press=True)
            if 'char' in params and params['char'] is not None:
                return params['char']
        except Exception:
            pass

        # 未知键码，返回 vk_ 格式
        return f'vk_{vk}'

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
        special_keys = KeyMapper._get_special_key_objects()
        if key_name in special_keys:
            return special_keys[key_name]

        # 单个字符按键
        if len(key_name) == 1:
            return keyboard.KeyCode.from_char(key_name)

        logger.warning(f"未知按键名称: {key_name}")
        return None
