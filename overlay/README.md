# CapsWriter recording status overlay

## 中文

Windows 可选录音状态悬浮窗。它从 CapsWriter 客户端日志读取录音状态，显示录音时长和实际触发的快捷键（例如“右 Alt 停止”）；录音结束后显示“正在识别…”，客户端完成输出后自动隐藏。窗口置顶、不激活、不抢键盘焦点，也不拦截鼠标。它不读取或保存识别文本，不增加键盘钩子、音频捕获或网络/API 调用。

在 Windows 上运行 `build.ps1` 编译，然后运行 `Launch-CapsWriter.ps1 -AppDir <CapsWriter安装目录>`。启动脚本以隐藏窗口方式启动 CapsWriter 客户端/服务端和状态窗。未提供 `-AppDir` 时，默认认为本目录位于 CapsWriter 安装目录下的 `overlay` 子目录。悬浮窗依赖 CapsWriter 2.6 的日志事件格式；升级版本后需重新验证事件匹配。

## English

An optional Windows recording-status overlay. It reads recording-state events from the CapsWriter client log, shows elapsed recording time and the shortcut actually used (for example, “Right Alt to stop”), changes to “Recognizing…” after recording, and hides after the client finishes output. The window stays on top without activation, keyboard focus, or mouse interception. It does not read or store transcript text and adds no keyboard hook, audio capture, network, or API calls.

On Windows, run `build.ps1` to compile, then run `Launch-CapsWriter.ps1 -AppDir <CapsWriter installation directory>`. The launcher starts the CapsWriter client/server and overlay hidden. Without `-AppDir`, it assumes this directory is an `overlay` subdirectory inside the CapsWriter installation. The overlay matches the CapsWriter 2.6 log event format and should be revalidated after upgrading CapsWriter.
