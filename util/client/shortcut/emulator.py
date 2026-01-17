# coding: utf-8
"""
按键模拟器

负责异步模拟键盘和鼠标按键输入
"""

from pynput import keyboard, mouse
from util.logger import get_logger
from util.client.shortcut.key_mapper import KeyMapper

logger = get_logger('client')


class KeyEmulator:
    """
    按键模拟器

    使用常驻的 controller 对象，避免重复创建开销
    """

    def __init__(self):
        """初始化模拟器"""
        self._keyboard_controller = keyboard.Controller()
        self._mouse_controller = mouse.Controller()
        self._emulating_keys = set()

    def is_emulating(self, key_name: str) -> bool:
        """检查是否正在模拟指定按键"""
        return key_name in self._emulating_keys

    def clear_emulating_flag(self, key_name: str) -> None:
        """清除模拟标志"""
        self._emulating_keys.discard(key_name)

    def emulate_key(self, key_name: str) -> None:
        """
        异步模拟键盘按键

        Args:
            key_name: 按键名称（如 'caps_lock', 'f12'）
        """
        try:
            self._emulating_keys.add(key_name)

            key_obj = KeyMapper.name_to_key(key_name)
            if key_obj is not None:
                self._keyboard_controller.press(key_obj)
                self._keyboard_controller.release(key_obj)
                logger.debug(f"[{key_name}] 补发按键成功")
            else:
                logger.warning(f"[{key_name}] 无法识别的按键，跳过补发")
        except Exception as e:
            logger.error(f"[{key_name}] 补发按键失败: {e}")

    def emulate_mouse_click(self, button_name: str) -> None:
        """
        异步模拟鼠标按键

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
