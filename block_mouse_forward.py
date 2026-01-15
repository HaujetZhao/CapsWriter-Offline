"""
阻塞鼠标侧键（前进键）和键盘 Caps Lock 事件

使用 pynput 监听鼠标和键盘事件，并阻止：
1. 鼠标前进侧键（X2 / Button.x2）
2. 键盘 Caps Lock 键

适用于防止误触鼠标侧键或 Caps Lock 导致的意外操作。

运行方式：
    python block_mouse_forward.py

退出方式：
    按 Ctrl+C 终止程序

依赖安装：
    pip install pynput

技术说明：
    - 使用 win32_event_filter 有选择性地抑制特定事件
    - 鼠标：Button.x1 为后退键，Button.x2 为前进键
    - 键盘：Caps Lock 的 VK 码为 0x14
"""

from pynput import mouse, keyboard
import sys


class InputBlocker:
    """输入设备阻塞器"""

    # Windows 鼠标消息常量
    WM_XBUTTONDOWN = 0x020B
    WM_XBUTTONUP = 0x020C
    WM_XBUTTONDBLCLK = 0x020D

    # XBUTTON 按键标识
    XBUTTON1 = 0x0001  # 后退键
    XBUTTON2 = 0x0002  # 前进键

    # Windows 键盘虚拟键码
    VK_CAPITAL = 0x14  # Caps Lock

    def __init__(self):
        """初始化阻塞器"""
        self.mouse_listener = None
        self.keyboard_listener = None

        # 统计计数器
        self.mouse_forward_blocked = 0
        self.mouse_back_detected = 0
        self.capslock_blocked = 0

    def create_mouse_filter(self):
        """
        创建鼠标 Windows 事件过滤器

        Returns:
            callable: 鼠标事件过滤函数
        """
        def win32_event_filter(msg, data):
            """
            鼠标事件过滤器

            Args:
                msg: Windows 消息类型
                data: MSLLHOOKSTRUCT 结构，包含鼠标数据

            Returns:
                bool: 返回 False 则隐藏该事件
            """
            # 检查是否为 XBUTTON 按键消息
            if msg in (self.WM_XBUTTONDOWN, self.WM_XBUTTONUP, self.WM_XBUTTONDBLCLK):
                # 提取 XBUTTON 标识（高位字）
                xbutton = (data.mouseData >> 16) & 0xFFFF

                if xbutton == self.XBUTTON2:
                    # 前进键（X2）- 阻塞
                    if msg == self.WM_XBUTTONDOWN:
                        self.mouse_forward_blocked += 1
                        print(f"🚫 已阻塞鼠标前进按键按下 #{self.mouse_forward_blocked}")
                    elif msg == self.WM_XBUTTONUP:
                        print(f"🚫 已阻塞鼠标前进按键松开 #{self.mouse_forward_blocked}")
                    # 调用 suppress_event() 阻止事件传递到系统
                    self.mouse_listener.suppress_event()
                    return False

                elif xbutton == self.XBUTTON1:
                    # 后退键（X1）- 仅记录，不阻塞
                    if msg == self.WM_XBUTTONDOWN:
                        self.mouse_back_detected += 1
                        print(f"⚠️  检测到鼠标后退按键按下 #{self.mouse_back_detected}")
                    elif msg == self.WM_XBUTTONUP:
                        print(f"⚠️  检测到鼠标后退按键松开 #{self.mouse_back_detected}")

            return True

        return win32_event_filter

    def create_keyboard_filter(self):
        """
        创建键盘 Windows 事件过滤器

        Returns:
            callable: 键盘事件过滤函数
        """
        def win32_event_filter(msg, data):
            """
            键盘事件过滤器

            Args:
                msg: Windows 消息类型（本过滤器基于 vkCode 判断，无需检查 msg）
                data: KBDLLHOOKSTRUCT 结构，包含键盘数据

            Returns:
                bool: 返回 False 则隐藏该事件
            """
            # 检查是否为 Caps Lock 键（通过虚拟键码判断）
            if data.vkCode == self.VK_CAPITAL:
                # 阻塞 Caps Lock 按键
                self.capslock_blocked += 1
                # 根据消息类型判断是按下还是松开
                if msg == 0x0100:  # WM_KEYDOWN
                    print(f"🚫 已阻塞 Caps Lock 按键按下 #{self.capslock_blocked}")
                elif msg == 0x0101:  # WM_KEYUP
                    print(f"🚫 已阻塞 Caps Lock 按键松开 #{self.capslock_blocked}")
                # 调用 suppress_event() 阻止事件传递到系统
                self.keyboard_listener.suppress_event()
                return False

            return True

        return win32_event_filter

    def on_mouse_click(self, _x, _y, _button, _pressed):
        """
        鼠标点击回调函数（空实现，所有处理都在过滤器中）

        Args:
            _x: 鼠标 X 坐标（未使用）
            _y: 鼠标 Y 坐标（未使用）
            _button: 按钮类型（未使用）
            _pressed: 是否按下（未使用）

        Returns:
            bool: 返回 False 则停止监听器
        """
        # 标记参数为有意不使用
        _ = _x, _y, _button, _pressed
        # 不显示普通按键，所有处理都在 win32_event_filter 中完成
        return True

    def on_key_press(self, _key):
        """
        键盘按下回调函数（空实现，所有处理都在过滤器中）

        Args:
            _key: 按下的键（未使用）

        Returns:
            bool: 返回 False 则停止监听器
        """
        # 标记参数为有意不使用
        _ = _key
        # 不显示普通按键，所有处理都在 win32_event_filter 中完成
        return True

    def start(self):
        """启动监听器"""
        print("=" * 60)
        print("🛡️  输入设备阻塞器已启动")
        print("=" * 60)
        print("✅ 鼠标前进侧键（X2）将被完全阻塞")
        print("✅ 键盘 Caps Lock 键将被完全阻塞")
        print("⚠️  鼠标后退侧键（X1）将被记录但不阻塞")
        print("📝 按 Ctrl+C 退出程序")
        print("=" * 60)
        print()

        # 创建鼠标监听器
        self.mouse_listener = mouse.Listener(
            on_click=self.on_mouse_click,
            win32_event_filter=self.create_mouse_filter()
        )

        # 创建键盘监听器
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            win32_event_filter=self.create_keyboard_filter()
        )

        # 启动两个监听器
        self.mouse_listener.start()
        self.keyboard_listener.start()

        try:
            # 保持程序运行
            self.mouse_listener.join()
            self.keyboard_listener.join()
        except KeyboardInterrupt:
            print("\n" + "=" * 60)
            print("👋 程序已退出")
            print(f"   阻塞鼠标前进按键: {self.mouse_forward_blocked} 次")
            print(f"   检测鼠标后退按键: {self.mouse_back_detected} 次")
            print(f"   阻塞 Caps Lock 按键: {self.capslock_blocked} 次")
            print("=" * 60)
        finally:
            self.stop()

    def stop(self):
        """停止监听器"""
        if self.mouse_listener and self.mouse_listener.running:
            self.mouse_listener.stop()
        if self.keyboard_listener and self.keyboard_listener.running:
            self.keyboard_listener.stop()
        print("🛑 监听器已停止")


def main():
    """主函数"""
    blocker = InputBlocker()

    # 设置控制台 UTF-8 编码（Windows 兼容）
    if sys.platform == "win32":
        import codecs

        # 确保 Windows 控制台正确显示中文
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            # Python < 3.7 的回退方案
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

    blocker.start()


if __name__ == "__main__":
    main()
