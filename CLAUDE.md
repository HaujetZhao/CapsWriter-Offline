# CapsWriter-Offline 开发指南

## 核心设计 (Core Design)
**"快、准、稳、离线"**
- **离线 (Offline)**: 全本地模型 (ASR, 标点, LLM)，保护隐私。
- **C/S 架构**: 
    - **Server**: 主进程处理 WebSocket，**独立子进程**运行 AI 模型（Sherpa-ONNX, Paraformer等），确保推理（CPU密集）不阻塞网络心跳。
    - **Client**: 轻量启动，负责全局快捷键监听、录音采集、UI 展示。
- **源代码开放**: `start_*.py` 为打包入口（冻结），`core_*.py` 为源码入口。发行版保留 `core_*.py` 供用户修改逻辑。
- **配置化**: `config.py` 及 `hot-*.txt` 位于根目录，支持热重载。

## 架构细节与流程 (Architecture & Workflows)

### 1. 识别全链路 (Recognition Flow)
- **采集**: Client 监听 CapsLock。按键时长 > **0.3s (Threshold)** 触发录音，**实时流式**通过 WebSocket 发送。
- **切片 (Slicing)**: Client 配置 `mic_seg_duration` (15s) 和 `mic_seg_overlap` (2s)。Server 仅基于时间切片，**禁用 VAD** 以保留完整上下文。
- **Server 处理**:
    - **双重结果**: 同时计算 `text` (简单文本拼接, Robust) 和 `text_accu` (基于 Token 时间戳去重, Precision)。
    - **拼接算法**: 优先使用 **Token 时间戳去重** (`util/server/text_merge.py`)，无时间戳则降级为 **模糊文本匹配**。
- **Client 后处理**:
    - **触发**: 用户**松开按键** -> Server 返回 IsFinal 结果。
    - **热词 (RAG)**: 基于 **音素 (Phoneme)** 的模糊检索，匹配 `hot.txt`（统一中英文热词）。
    - **上屏**: 模拟键盘输入或写入剪贴板 ("松开即出")。

### 2. 客户端模式 (Client Modes)
- **听写 (Dictation)**: 默认模式。按住快捷键 -> 流式识别 -> 松开上屏。
- **转录 (Transcription)**: 拖入文件 -> `ffmpeg` 提取音频 -> 发送 Server -> 接收带时间戳结果 -> 生成 `.srt`。

### 3. LLM Agent & 智能修正
- **实时监控 (Hot Reload)**: Client 启动文件监视器，实时响应 `hot.txt`、`hot-rectify.txt` 和 `LLM/*.py` 的修改。
- **Trigger**: 检测识别结果前缀（如“翻译”），匹配 `LLM/` 下定义的角色。
- **Context 组装**（根据角色配置决定是否启用）:
    1.  **历史纠错**: RAG 检索 `hot-rectify.txt` 历史修正库（`enable_rectify_history`）。
    2.  **潜在热词**: RAG 检索 `hot.txt`（`enable_hotwords`）。
    3.  **选中文字**: 模拟 Ctrl+C 获取的鼠标选中文本（`enable_read_selection`）。
    4.  **用户指令**: 当前语音输入内容。
- **UI**: 结果流式显示在 **Toast** (Tkinter 无边框置顶窗)，支持 Markdown 渲染。

### 4. 历史归档 (Diary)
- **按日期归档**: `年份/月份/日期.md`。
- **音频**: 原始录音存入 `年份/月份/assets/`，Markdown 中自动生成 HTML 音频控件链接。

## 关键路径 (Key Paths)
- **配置**: `config.py` (根目录).
- **热词**: `hot.txt` (统一 RAG 音素匹配), `hot-rule.txt` (规则替换), `hot-rectify.txt` (历史修正 RAG).
- **LLM角色**: `LLM/*.py` (根目录, 定义 Role/Prompt/Model).
- **逻辑核心**: `util/` (含 `client`, `server`, `llm`, `hotword` 等子模块).
- **日志**: `log/client.log` & `log/server.log` (排查问题唯一入口).
- **协议**: `util/protocol.py`.

## 打包与部署 (Build)
- `build.spec`: Server + Client 打包。
- `build-client.spec`: 仅 Client (Win7兼容)。
- **策略**: 所有 Python 依赖放入 `internal/`。根目录仅保留配置文件、源码入口 (`core_*.py`)、模型文件夹 (`models/`) 和说明文档。

## 用户偏好 (User Preferences)
- **语言**: 中文 (Chinese)，总结、Plan、WalkThrough、注释都要用中文。
- **路径链接**: 总结时文件必须显示为相对路径链接（精确到行，便于点击跳转）。
- **系统**: Windows 10, PowerShell (命令行分隔符 `;`).
- **环境**: 运行前确保 `conda activate capswriter`.