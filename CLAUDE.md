# CapsWriter-Offline 开发指南

## 核心设计 (Core Design)
**"快、准、稳、离线"**
- **离线 (Offline)**: 全本地模型 (ASR, 标点, LLM)，保护隐私。
- **C/S 架构**:
    - **Server**: 主进程处理 WebSocket，**独立子进程** (`multiprocessing.Process`) 运行 AI 模型，确保推理（CPU密集）不阻塞网络心跳。
    - **Client**: 轻量启动，负责全局快捷键监听、录音采集、UI 展示。
- **源代码开放**: 入口 [`start_server.py`](start_server.py) / [`start_client.py`](start_client.py) 为冻结入口；核心源码在 [`core/`](core/) 目录，发行版保留为源码供用户修改。
- **配置化**: [`config_client.py`](config_client.py) / [`config_server.py`](config_server.py) 及 `hot*.txt`、[`LLM/*.py`](LLM/) 位于根目录。
- **版本**: v2.5-alpha（2026-04-28）

## 架构细节与流程 (Architecture & Workflows)

### 1. 识别全链路 (Recognition Flow)
- **采集**: Client 监听快捷键（默认 CapsLock 和 X2）。按下就开始收集录音chunk，超过 **0.3s (Threshold)** 不松则触发识别，**实时流式**通过 WebSocket 发送。
- **切片 (Slicing)**: Client 配置 `mic_seg_duration` (60s) 和 `mic_seg_overlap` (4s)。Server 仅基于时间切片，**禁用 VAD** 以保留完整上下文。
- **Server 处理**:
    - **双重结果**: 同时计算 `text` (简单文本拼接, Robust) 和 `text_accu` (基于 Token 时间戳去重, Precision)。
    - **拼接算法**: `text_accu`使用 **Token 时间戳去重** ([`core/server/merger/`](core/server/merger/))，`text` 使用 **模糊文本匹配**。
- **Client 后处理**:
    - **触发**: 用户**松开按键** -> Server 返回 IsFinal 结果。
    - **热词 (RAG)**: 基于 **音素 (Phoneme)** 的两阶段模糊检索，匹配 `hot.txt`（统一中英文热词）。
    - **规则替换**: `hot-rule.txt` 正则替换。
    - **LLM 润色**: 根据角色配置进行智能润色或回答。
    - **上屏**: 模拟键盘输入或 Toast 显示。

### 2. 客户端模式 (Client Modes)
- **听写 (Dictation)**: 默认模式。按住快捷键 -> 发送音频 -> 松开上屏。
- **转录 (Transcription)**: 拖入文件 -> `ffmpeg` 提取音频 -> 发送 Server -> 接收带时间戳结果 -> 生成 `.srt` / `.txt` / `.json`。

### 3. LLM Agent & 智能修正
- **实时监控 (Hot Reload)**: Client 启动 `watchdog` 文件监视器，实时响应 `hot*.txt` 和 `LLM/*.py` 的修改（3秒防抖）。
- **角色系统**: 模块化的 LLM 角色配置，支持多角色切换。
- **角色触发**: 检测识别结果前缀（如"翻译"、"助理"），匹配 [`LLM/`](LLM/) 下定义的角色。
- **Context 组装**（根据角色配置决定是否启用）:
    1.  **潜在热词**: RAG 检索 `hot.txt`（`enable_hotwords`）。
    2.  **选中文字**: 模拟 Ctrl+C 获取的鼠标选中文本（`enable_read_selection`）。
    3.  **对话历史**: 保留上下文历史记录（`enable_history`）。
    4.  **用户指令**: 当前语音输入内容。
- **输出模式**:
    - **typing**: 直接模拟键盘打字输出。
    - **toast**: 在 Toast 弹窗中显示，支持 Markdown 渲染。
- **UI**: 结果流式显示在 **Toast** (Tkinter 无边框置顶窗)，支持 Markdown 渲染。

### 4. 热词系统 (Hotword System)
- **服务器热词**: `hot-server.txt` 用于服务端热词增强。
- **统一文件**: `hot.txt` 统一管理中英文热词（基于音素匹配）。
- **两阶段检索**:
    1.  **FastRAG**: 倒排索引 + Numba JIT 快速粗筛（减少 90% 计算量）。
    2.  **AccuRAG**: 模糊音权重精确匹配（前后鼻音、平翘舌等）。
- **双阈值机制**:
    - `hot_thresh` (0.85): 高阈值用于实际替换。
    - `hot_similar` (0.6): 低阈值用于 LLM 上下文参考。
- **规则替换**: `hot-rule.txt` 支持正则表达式规则替换 (`pattern = replacement`)。

### 5. 历史归档 (Diary)
- **按日期归档**: `年份/月份/日期.md`。
- **音频**: 原始录音存入 `年份/月份/assets/`，Markdown 中自动生成 HTML 音频控件链接。

### 6. UDP 广播与控制
- **UDP 广播**: 识别结果可通过 UDP 广播到局域网（`udp_broadcast=True`）。
- **UDP 控制**: 支持通过 UDP 命令远程控制录音启停（`udp_control=True`）。

## 关键路径 (Key Paths)
- **服务端配置**: [`config_server.py`](config_server.py) — 模型选择、网络、格式化、对齐器。
- **客户端配置**: [`config_client.py`](config_client.py) — 快捷键、音频、热词、LLM、输出、UDP。
- **热词**:
    - [`hot.txt`](hot.txt) - 统一 RAG 音素匹配（中英文）
    - [`hot-rule.txt`](hot-rule.txt) - 规则替换
    - [`hot-server.txt`](hot-server.txt) - 服务端热词
- **LLM角色**: [`LLM/*.py`](LLM/) (根目录, 定义 Role/Prompt/Model)
    - [`default.py`](LLM/default.py) - 默认角色（热词、润色，process=False）
    - [`翻译.py`](LLM/翻译.py) - 翻译角色（ollama/gemma3:12b）
    - [`高级翻译.py`](LLM/高级翻译.py) - 高级翻译（deepseek/deepseek-chat）
    - [`大助理.py`](LLM/大助理.py) - 大助理（zhipu/glm-4.5-air）
    - [`小助理.py`](LLM/小助理.py) - 小助理（lmstudio/local-model）
- **服务端核心**: [`core/server/`](core/server/)
    - [`app.py`](core/server/app.py) - `CapsWriterServer` 门面类
    - [`state.py`](core/server/state.py) - `ServerState` / `WorkerState` 共享状态
    - [`schema.py`](core/server/schema.py) - `Task` / `Result` / `RecognitionSession` 数据结构
    - [`connection/server_manager.py`](core/server/connection/server_manager.py) - `SocketManager` WebSocket 服务端生命周期
    - [`connection/ws_recv.py`](core/server/connection/ws_recv.py) - 音频接收与切片
    - [`connection/ws_send.py`](core/server/connection/ws_send.py) - 识别结果发送
    - [`worker/process_manager.py`](core/server/worker/process_manager.py) - `ProcessManager` 子进程管理
    - [`worker/worker.py`](core/server/worker/worker.py) - `RecognizerWorker` 推理循环
    - [`worker/model_loader.py`](core/server/worker/model_loader.py) - `ModelLoader` 模型加载
    - [`worker/pipeline.py`](core/server/worker/pipeline.py) - `TaskPipeline` 识别流水线
    - [`engines/`](core/server/engines/) - ASR 引擎实现（见下方模型支持）
    - [`merger/`](core/server/merger/) - 文本/Token 合并算法
    - [`formatter/text_formatter.py`](core/server/formatter/text_formatter.py) - `TextFormatter` 后处理
- **客户端核心**: [`core/client/`](core/client/)
    - [`app.py`](core/client/app.py) - `CapsWriterClient` 门面类
    - [`state.py`](core/client/state.py) - `ClientState` 共享状态
    - [`connection/websocket_manager.py`](core/client/connection/websocket_manager.py) - `WebSocketManager`
    - [`audio/`](core/client/audio/) - `AudioStreamManager` / `Recorder` / `FileManager`
    - [`shortcut/`](core/client/shortcut/) - `ShortcutManager`（pynput）快捷键系统
    - [`output/result_processor.py`](core/client/output/result_processor.py) - `ResultProcessor` 后处理核心
    - [`output/text_output.py`](core/client/output/text_output.py) - `TextOutput` 上屏
    - [`hotword/`](core/client/hotword/) - 热词系统（Phoneme RAG + Rule + Rectification）
    - [`llm/`](core/client/llm/) - LLM 子系统（角色加载、上下文、API 调用）
    - [`manager/`](core/client/manager/) - `MicRunner` / `FileRunner` / `TrayManager`
    - [`transcribe/`](core/client/transcribe/) - `FileTranscriber` 文件转录
    - [`diary/diary_writer.py`](core/client/diary/diary_writer.py) - `DiaryWriter` 日记归档
    - [`udp/`](core/client/udp/) - UDP 广播与远程控制
- **共享工具**: [`core/tools/`](core/tools/) — ITN、格式化、信号处理、窗口检测、简繁转换
- **UI 组件**: [`core/ui/`](core/ui/) — Toast、Tray、对话框（热词/纠错）
- **协议**: [`core/protocol.py`](core/protocol.py) — `AudioMessage` + `RecognitionMessage`
- **日志**: `logs/client_latest.log` & `logs/server_latest.log`（排查问题唯一入口）

## 打包与部署 (Build)
- [`build.spec`](build.spec): Server + Client 打包。
- [`build-client.spec`](build-client.spec): 仅 Client (Win7兼容)。
- **策略**: 所有 Python 依赖放入 `internal/`。根目录仅保留配置文件、源码入口 ([`start_*.py`](start_server.py))、核心源码 ([`core/`](core/))、模型文件夹 ([`models/`](models/)) 和说明文档。
- **PyInstaller 6.0+**: 使用现代化打包配置，支持 CUDA provider 可选收集。

## 模型支持 (Models)

### ASR 引擎

| 引擎类型 | 类名 | 文件 | 能力 | 说明 |
|---------|------|------|------|------|
| `paraformer` | `ParaformerEngine` | [`engines/paraformer_onnx/`](core/server/engines/paraformer_onnx/) | ASR + TIMESTAMPS | 通过 `sherpa_onnx.OfflineRecognizer`，准确率高 |
| `sensevoice` | `SenseVoiceEngine` | [`engines/sensevoice_onnx/`](core/server/engines/sensevoice_onnx/) | ASR + PUNC + HOTWORDS + TIMESTAMPS | 自有 ONNX 推理，多语言（中英日韩粤） |
| `fun_asr_nano` | `FunASREngine` | [`engines/fun_asr_gguf/`](core/server/engines/fun_asr_gguf/) | ASR + PUNC + HOTWORDS + TIMESTAMPS | GGUF LLM 解码器 + ONNX 编码器/CTC，最准 |
| `qwen_asr` | `QwenASREngine` | [`engines/qwen_asr_gguf/`](core/server/engines/qwen_asr_gguf/) | ASR + PUNC | GGUF 版 Qwen3-ASR 模型 |

### 辅助模型
- **Punct-CT-Transformer**: 标点模型（`CTTransformerPuncEngine`），引擎无 PUNC 能力时自动加载。
- **QwenForceAligner**: 对齐器（`ManagedAlignerProxy` 延迟加载+闲置卸载），用于文件转录时间戳对齐。

### 引擎能力检测
引擎通过 `EngineCapabilities` 标志位声明能力（`ASR` / `PUNC` / `TIMESTAMPS` / `STREAMING` / `HOTWORDS`）。`ModelLoader` 在加载时智能补丁：若引擎缺少 `PUNC` 则外挂标点模型，若缺少 `TIMESTAMPS` 则外挂对齐器。

## LLM 提供商支持 (LLM Providers)
- **Ollama**: 本地部署（默认）。
- **LMStudio**: 本地 OpenAI 兼容 API。
- **OpenAI**: GPT 系列。
- **DeepSeek**: deepseek 系列。
- **Moonshot**: 月之暗面。
- **Zhipu**: 智谱 AI。
- **Volcengine**: 火山引擎。
- **Cerebras**: Cerebras。

## 数据流 (Data Flow)
```
[Microphone] -> sounddevice callback -> asyncio.Queue
   |
   v  (ShortcutManager 检测按键)
[AudioStreamManager] 开始录音 -> WebSocketManager 发送 AudioMessage (base64 chunks)
   |
   v  (WebSocket, 子协议 "binary")
[Server: SocketManager] -> ws_recv -> AudioCache 切片 -> Task -> multiprocessing.Queue
   |
   v
[Worker 子进程: RecognizerWorker]
   |-- TaskPipeline: 音频预处理 -> ASR 解码 -> 文本合并 -> 格式化
   |-- 输出两路结果: text (简单合并) + text_accu (时间戳去重)
   |
   v
[Server: ws_send] -> RecognitionMessage -> WebSocket -> Client
   |
   v
[Client: ResultProcessor]
   |-- 音素热词纠正 (FastRAG + AccuRAG)
   |-- 正则规则替换 (hot-rule.txt)
   |-- LLM 角色检测 -> 上下文组装 -> API 调用 -> 流式输出
   |-- TextOutput 上屏 (type/paste) 或 Toast 显示
   |-- DiaryWriter 日记归档
   |-- UDP 广播识别结果
```

## 用户偏好 (User Preferences)
- **语言**: 中文 (Chinese)，总结、Plan、WalkThrough、注释都要用中文。
- **环境**: 运行环境是 `conda activate c`，或用 `D:/anaconda3/envs/c/python.exe` 或 `conda run -n c` 执行。所有的临时 Python 代码要先写到临时脚本文件，再运行，而不要直接用命令行跑代码。临时脚本用完不要删。

