# CapsWriter-Offline 开发指南

## 核心设计 (Core Design)
**"快、准、稳、离线"**
- **离线 (Offline)**: 全本地模型 (ASR, 标点, LLM)，保护隐私。
- **C/S 架构**:
    - **Server**: 主进程处理 WebSocket，**独立子进程**运行 AI 模型（Sherpa-ONNX, Paraformer等），确保推理（CPU密集）不阻塞网络心跳。
    - **Client**: 轻量启动，负责全局快捷键监听、录音采集、UI 展示。
- **源代码开放**: `start_*.py` 为打包入口（冻结），`core_*.py` 为源码入口。发行版保留 `core_*.py` 供用户修改逻辑。
- **配置化**: `config.py` 及 `hot*.txt`、`LLM/*.py` 位于根目录，支持热重载。
- **版本**: v2.1（2026-01-13）

## 架构细节与流程 (Architecture & Workflows)

### 1. 识别全链路 (Recognition Flow)
- **采集**: Client 监听 CapsLock。按键时长 > **0.3s (Threshold)** 触发录音，**实时流式**通过 WebSocket 发送。
- **切片 (Slicing)**: Client 配置 `mic_seg_duration` (25s) 和 `mic_seg_overlap` (2s)。Server 仅基于时间切片，**禁用 VAD** 以保留完整上下文。
- **Server 处理**:
    - **双重结果**: 同时计算 `text` (简单文本拼接, Robust) 和 `text_accu` (基于 Token 时间戳去重, Precision)。
    - **拼接算法**: 优先使用 **Token 时间戳去重** ([`util/server/text_merge.py`](util/server/text_merge.py))，无时间戳则降级为 **模糊文本匹配**。
- **Client 后处理**:
    - **触发**: 用户**松开按键** -> Server 返回 IsFinal 结果。
    - **热词 (RAG)**: 基于 **音素 (Phoneme)** 的两阶段模糊检索，匹配 `hot.txt`（统一中英文热词）。
    - **LLM 润色**: 根据角色配置进行智能修正和润色。
    - **上屏**: 模拟键盘输入或写入剪贴板 ("松开即出")。

### 2. 客户端模式 (Client Modes)
- **听写 (Dictation)**: 默认模式。按住快捷键 -> 流式识别 -> 松开上屏。
- **转录 (Transcription)**: 拖入文件 -> `ffmpeg` 提取音频 -> 发送 Server -> 接收带时间戳结果 -> 生成 `.srt`。

### 3. LLM Agent & 智能修正
- **实时监控 (Hot Reload)**: Client 启动文件监视器，实时响应 `hot*.txt` 和 `LLM/*.py` 的修改。
- **角色系统**: 模块化的 LLM 角色配置，支持多角色切换。
- **角色触发**: 检测识别结果前缀（如"翻译"、"助理"），匹配 [`LLM/`](LLM/) 下定义的角色。
- **Context 组装**（根据角色配置决定是否启用）:
    1.  **历史纠错**: RAG 检索 `hot-rectify.txt` 历史修正库（`enable_rectify`）。
    2.  **潜在热词**: RAG 检索 `hot.txt`（`enable_hotwords`）。
    3.  **选中文字**: 模拟 Ctrl+C 获取的鼠标选中文本（`enable_read_selection`）。
    4.  **对话历史**: 保留上下文历史记录（`enable_history`）。
    5.  **用户指令**: 当前语音输入内容。
- **输出模式**:
    - **typing**: 直接模拟键盘打字输出。
    - **toast**: 在 Toast 弹窗中显示，支持 Markdown 渲染。
- **UI**: 结果流式显示在 **Toast** (Tkinter 无边框置顶窗)，支持 Markdown 渲染。

### 4. 热词系统 (Hotword System)
- **统一文件**: `hot.txt` 统一管理中英文热词（基于音素匹配）。
- **两阶段检索**:
    1.  **FastRAG**: 倒排索引 + Numba JIT 快速粗筛（减少 90% 计算量）。
    2.  **AccuRAG**: 模糊音权重精确匹配（前后鼻音、平翘舌等）。
- **双阈值机制**:
    - `hot_thresh` (0.85): 高阈值用于实际替换。
    - `hot_similar` (0.65): 低阈值用于 LLM 上下文参考。
- **规则替换**: `hot-rule.txt` 支持正则表达式规则替换。
- **纠错历史**: `hot-rectify.txt` 保存和检索历史修正记录。

### 5. 历史归档 (Diary)
- **按日期归档**: `年份/月份/日期.md`。
- **音频**: 原始录音存入 `年份/月份/assets/`，Markdown 中自动生成 HTML 音频控件链接。
- **关键词日记**: 识别结果以关键词开头时，归档到 `年份/月份/关键词-日期.md`。

## 关键路径 (Key Paths)
- **配置**: [`config.py`](config.py) (根目录).
- **热词**:
    - [`hot.txt`](hot.txt) - 统一 RAG 音素匹配（中英文）
    - [`hot-rule.txt`](hot-rule.txt) - 规则替换
    - [`hot-rectify.txt`](hot-rectify.txt) - 历史修正 RAG
- **LLM角色**: [`LLM/*.py`](LLM/) (根目录, 定义 Role/Prompt/Model)
    - [`default.py`](LLM/default.py) - 默认角色（热词、润色）
    - [`翻译.py`](LLM/翻译.py) - 翻译角色
    - [`高级翻译.py`](LLM/高级翻译.py) - 高级翻译
    - [`Python.py`](LLM/Python.py) - Python 编程助手
    - [`命令.py`](LLM/命令.py) - 命令执行
    - [`大助理.py`](LLM/大助理.py) - 大助理
    - [`小助理.py`](LLM/小助理.py) - 小助理
- **逻辑核心**: [`util/`](util/) (含 `client`, `server`, `llm`, `hotword` 等子模块).
    - [`util/client/`](util/client/) - 客户端工具（音频、输入、处理、UI）
    - [`util/server/`](util/server/) - 服务端工具（WebSocket、识别、拼接）
    - [`util/llm/`](util/llm/) - LLM 处理（角色、上下文、输出）
    - [`util/hotword/`](util/hotword/) - 热词管理（RAG、规则、纠错）
- **日志**: `log/client.log` & `log/server.log` (排查问题唯一入口).
- **协议**: [`util/protocol.py`](util/protocol.py).

## 打包与部署 (Build)
- [`build.spec`](build.spec): Server + Client 打包。
- [`build-client.spec`](build-client.spec): 仅 Client (Win7兼容).
- **策略**: 所有 Python 依赖放入 `internal/`。根目录仅保留配置文件、源码入口 ([`core_*.py`](core_client.py))、模型文件夹 ([`models/`](models/)) 和说明文档。
- **PyInstaller 6.0+**: 使用现代化打包配置，支持 CUDA provider 可选收集。

## 模型支持 (Models)
- **FunASR-Nano**: 轻量级模型，速度快（推荐）。
    - 下载: `sherpa-onnx-funasr-nano-int8-2025-12-30.tar.bz2`
- **SenseVoice**: 多语言支持（中英日韩粤）。
    - 下载: `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2`
- **Paraformer**: 大模型，准确率高。
- **Punct-CT-Transformer**: 标点模型。
- **FireRed**: 大模型（未使用）。

## LLM 提供商支持 (LLM Providers)
- **Ollama**: 本地部署（默认）。
- **OpenAI**: GPT 系列。
- **DeepSeek**: deepseek 系列。
- **Moonshot**: 月之暗面。
- **Zhipu**: 智谱 AI。
- **Claude**: Anthropic Claude。
- **Gemini**: Google Gemini。

## 用户偏好 (User Preferences)
- **语言**: 中文 (Chinese)，总结、Plan、WalkThrough、注释都要用中文。
- **路径链接**: 总结时文件必须显示为相对路径链接（精确到行，便于点击跳转）。
- **系统**: Windows 10, PowerShell (命令行分隔符 `;`).
- **环境**: 运行前确保 `conda activate capswriter`，或用 `D:\anaconda3\envs\capswriter\python.exe` 执行，新建测试脚本要手动指定 console utf-8 输出。

## 最新更新 (Recent Updates)
- **2026-01-12**: 语音切片加长至 25 秒。
- **角色模板**: 完善角色配置模板文档 ([`LLM/__init__.py`](LLM/__init__.py))。
- **音素 RAG**: 两阶段检索优化性能。
- **LLM 集成**: 支持多提供商、多角色、上下文管理。
- **UI 增强**: Toast 弹窗支持 Markdown 渲染和自定义样式。
- **热词统一**: 中英文热词统一到 `hot.txt`。
- **生命周期管理**: 优化退出处理和资源清理。
- **错误处理**: 改进 WebSocket 连接错误处理。
