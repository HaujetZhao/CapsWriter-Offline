# Research: CapsWriter-Offline GUI 配置工具

## 技术决策记录

### 1. GUI 框架选择

**决策**: 使用 **tkinter + ttkbootstrap**

**理由**:
- tkinter 是 Python 标准库，**无需额外安装**，符合项目轻量化原则
- ttkbootstrap 提供现代化主题，支持深色模式，**提升视觉体验**
- 项目已有 Rich 库用于控制台输出，风格可保持一致
- 相比 PyQt/PySide，tkinter **不增加打包体积**（约 50MB vs 200MB+）

**考虑的替代方案**:
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| PyQt5/PySide6 | 功能强大，跨平台 | 打包体积大，依赖复杂 | ❌ 不采用 |
| wxPython | 原生风格 | 社区较小，文档少 | ❌ 不采用 |
| tkinter 原生 | 零依赖 | 外观过时 | ⚠️ 备选 |
| **tkinter + ttkbootstrap** | 现代外观，轻量 | 需额外安装一个包 | ✅ 采用 |
| Dear PyGui | 高性能 | 学习曲线陡 | ❌ 不采用 |

---

### 2. 配置持久化策略

**决策**: 采用 **config.json + config.py 双轨制**

**理由**:
- 现有 `config.py` 是 Python 类，**难以安全读写**（需 AST 解析或 exec）
- 新增 `config.json` 存储 GUI 可配置项，**结构化且安全**
- 启动时优先读取 `config.json`，覆盖 `config.py` 默认值
- 保持向后兼容：没有 `config.json` 时仍使用 `config.py`

**配置加载优先级**:
```
config.py (Python 默认值)
    ↓ 覆盖
config.json (用户 GUI 配置)
    ↓ 覆盖
命令行参数 (如有)
```

**考虑的替代方案**:
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 直接修改 config.py | 兼容现有 | 复杂，易出错 | ❌ 风险高 |
| YAML 配置 | 可读性好 | 需额外依赖 | ⚠️ 备选 |
| **JSON 配置** | 标准库支持 | 不支持注释 | ✅ 采用 |
| TOML 配置 | Python 3.11+ 标准 | 需考虑兼容性 | ❌ 暂不采用 |

---

### 3. 快捷键角色绑定实现

**决策**: 扩展 `Shortcut` 数据类，添加 `role` 字段

**理由**:
- 最小化代码改动，**只需修改一个文件**
- 兼容现有快捷键配置（role 字段可选，默认 None）
- 无需修改 `ShortcutManager` 核心逻辑，只需在触发时传递 role

**实现方案**:
```python
# util/client/shortcut/shortcut_config.py
@dataclass
class Shortcut:
    key: str
    type: Literal['keyboard', 'mouse'] = 'keyboard'
    suppress: bool = False
    hold_mode: bool = True
    threshold: Optional[float] = None
    enabled: bool = True
    role: Optional[str] = None  # 🆕 绑定的 LLM 角色名（如 "翻译", "大助理"）
```

**传递机制**:
1. `ShortcutTask` 触发时读取 `shortcut.role`
2. 如果 role 非空，将其传递给 LLM 处理流程
3. LLM 角色加载器优先使用指定 role，跳过前缀匹配

---

### 4. 状态悬浮窗实现方案

**决策**: 使用 **tkinter Toplevel + 透明背景 + 置顶**

**理由**:
- tkinter 原生支持 `overrideredirect` 无边框窗口
- Windows 上支持 `-alpha` 透明度设置
- 可通过 `-topmost` 属性始终置顶

**技术细节**:
```python
root = tk.Toplevel()
root.overrideredirect(True)       # 无边框
root.attributes('-topmost', True)  # 置顶
root.attributes('-alpha', 0.85)    # 透明度
root.wm_attributes('-transparentcolor', 'systemTransparent')  # 透明穿透
```

**状态通信机制**:
```
ClientState (状态变更)
    ↓ 事件驱动
StatusOverlay (UI 更新)
    ↓ 定时刷新
录音时长显示 (每 100ms)
```

---

### 5. Ollama 模型列表获取

**决策**: 调用 `ollama list` + HTTP API 备选

**理由**:
- CLI 方式简单直接，无需额外依赖
- HTTP API (`http://localhost:11434/api/tags`) 可作为备选

**实现**:
```python
def get_ollama_models() -> List[str]:
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过表头
            return [line.split()[0] for line in lines if line]
    except Exception:
        pass
    return []  # Ollama 未安装或无模型
```

---

### 6. 悬浮窗与主程序通信

**决策**: 使用 **线程安全队列 + tkinter after() 轮询**

**理由**:
- tkinter 不是线程安全的，需在主线程更新 UI
- 使用 `queue.Queue` 跨线程传递状态
- `after()` 定时轮询队列，更新 UI

**架构**:
```
┌─────────────────┐    Queue    ┌─────────────────┐
│ ShortcutManager │ ──────────> │  StatusOverlay  │
│  (工作线程)      │   状态事件   │  (UI 主线程)     │
└─────────────────┘             └─────────────────┘
        │                               ↑
        └── 通过 state.recording ───────┘
```

---

## 技术风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| tkinter 在某些 Windows 版本样式异常 | 低 | 使用 ttkbootstrap 标准化主题 |
| config.json 与 config.py 冲突 | 中 | 明确优先级，测试边界情况 |
| 悬浮窗遮挡用户操作 | 低 | 支持位置配置 + 自动淡出 |
| Ollama 未安装时 | 低 | 显示友好提示，允许手动输入模型名 |
| 快捷键捕获与系统冲突 | 中 | 复用现有 pynput 机制，已验证稳定 |

---

## 依赖清单

### 新增依赖
| 包名 | 版本 | 用途 |
|------|------|------|
| ttkbootstrap | >=1.10 | 现代化 tkinter 主题 |

### 现有依赖（无需新增）
| 包名 | 用途 |
|------|------|
| pynput | 快捷键捕获（GUI 按键绑定） |
| tkinter | GUI 框架（Python 标准库） |

---

## 结论

本方案采用**轻量化、低侵入**原则：
- GUI 框架选择 tkinter + ttkbootstrap，**零额外大型依赖**
- 配置持久化采用 JSON，**不修改现有 config.py 结构**
- 快捷键角色绑定通过扩展数据类实现，**最小改动**
- 状态悬浮窗使用标准 tkinter 特性，**无平台特定代码**

预计新增代码量：**500-700 行**
