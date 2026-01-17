# coding: utf-8
"""
按键映射相关

处理按键名称和虚拟键码之间的转换，以及相关常量定义
"""

from pynput import keyboard
from util.logger import get_logger

logger = get_logger('client')

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

# 虚拟键码映射表
VK_CODE_MAP = {
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

# 按键码范围
VK_NUMBER_RANGE = (0x30, 0x39)  # 0-9
VK_LETTER_RANGE = (0x41, 0x5A)  # A-Z


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
        # 首先查表
        if vk in VK_CODE_MAP:
            return VK_CODE_MAP[vk]

        # 数字 0-9
        if VK_NUMBER_RANGE[0] <= vk <= VK_NUMBER_RANGE[1]:
            return str(vk - VK_NUMBER_RANGE[0])

        # 字母 A-Z
        if VK_LETTER_RANGE[0] <= vk <= VK_LETTER_RANGE[1]:
            return chr(vk).lower()

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
