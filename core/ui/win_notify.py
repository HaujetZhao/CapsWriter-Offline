# coding: utf-8
"""
Windows 系统通知模块（识别失败专用）

把"识别失败"从项目自带的浮动窗（红底白字、屏幕中间弹出）改为
Windows 右下角系统通知（action center 气泡），避免打断正在输入的用户。

实现说明：
- 零第三方依赖：直接用 subprocess 调 powershell.exe（Windows PowerShell 5.1）
  内联 WinRT toast。WinRT toast 类型在 PS 5.1 下可加载，pwsh 7 不行，故固定用
  powershell.exe。已在 Win10 26300 实测：toast 成功显示，无残留进程。
- 平台检测：Windows 10 及以上有原生 toast；Win7 无 toast（Win8.1 才有），
  自动回退到项目自带浮动窗，不破坏 Win7 兼容（build-client.spec 明确为 Win7 打包）。
- 每个通知起一个 powershell.exe 进程（~200-500ms，后台无窗口，不阻塞调用方）。

Usage:
    from core.ui.win_notify import show_asr_error_notification
    show_asr_error_notification("识别失败: TimeoutError: timed out")
"""

from __future__ import annotations

import platform
import subprocess
import sys

from . import logger


# WinRT toast 模板（对齐 winotify 的 ToastImageAndText02，简洁版）
_TOAST_TEMPLATE = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$Template = @"
<toast duration="short">
    <visual>
        <binding template="ToastImageAndText02">
            <text id="1"><![CDATA[{title}]]></text>
            <text id="2"><![CDATA[{msg}]]></text>
        </binding>
    </visual>
</toast>
"@
$SerializedXml = New-Object Windows.Data.Xml.Dom.XmlDocument
$SerializedXml.LoadXml($Template)
$Toast = [Windows.UI.Notifications.ToastNotification]::new($SerializedXml)
$Notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_id}")
$Notifier.Show($Toast)
"""

_APP_ID = "CapsWriter-Offline"


def _windows_major() -> int:
    """返回 Windows 主版本号（如 11）；非 Windows 或获取失败返回 0"""
    if sys.platform != "win32":
        return 0
    try:
        return int(platform.win32_ver()[0] or 0)
    except Exception:
        return 0


def _ps_escape(text: str) -> str:
    """转义要注入 PowerShell here-string 的文本，避免变量展开/转义符破坏。

    here-string（@"..."@）里的 $ 会触发变量展开，反引号是转义符，]]> 会提前
    闭合 CDATA。逐一处理：$ → `$（反引号转义）、` → ``、]]> → 拆开。
    """
    return (
        (text or "")
        .replace("`", "``")
        .replace("$", "`$")
        .replace("]]>", "]] >")
    )


def _supports_toast() -> bool:
    """系统 toast 通知需要 Win8.1 及以上（Win10 为稳妥阈值）"""
    return _windows_major() >= 10


def show_system_toast(title: str, msg: str) -> bool:
    """用 Windows 右下角系统通知显示一条消息。

    Returns:
        True 表示成功发起（进程已启动）；False 表示失败/平台不支持。
    """
    if not _supports_toast():
        return False
    try:
        script = _TOAST_TEMPLATE.format(
            title=_ps_escape(title),
            msg=_ps_escape(msg),
            app_id=_APP_ID,
        )
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=si,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception as e:
        logger.warning(f"系统通知显示失败，回退浮动窗: {e}")
        return False


def show_asr_error_notification(error: str) -> None:
    """显示识别失败通知：Win10+ 走系统通知，否则回退项目自带浮动窗。

    Args:
        error: 服务端上报的识别失败原因（如 "TimeoutError: timed out"）。
    """
    text = (error or "")[:120]

    # 优先系统 toast（右下角，不打断输入）
    if _supports_toast():
        if show_system_toast("识别失败", text):
            return
        # 系统通知失败才回退浮动窗

    # Win7 或无 toast 时：回退项目自带浮动窗（保持原有行为）
    try:
        from core.ui.toast import toast

        toast(f"识别失败: {text}")
    except Exception as e:
        logger.error(f"识别失败通知显示失败: {e}")


if __name__ == "__main__":
    # 手动测试：python core/ui/win_notify.py
    show_asr_error_notification("TimeoutError: timed out（测试）")
