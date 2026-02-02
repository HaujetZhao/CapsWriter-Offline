# Implementation Plan: CapsWriter-Offline GUI 配置工具

## 1. 技术上下文

### 现有架构

本项目基于现有 CapsWriter-Offline v2.3 架构进行扩展：

**受影响的组件**:
| 组件 | 文件路径 | 改动类型 |
|------|----------|----------|
| 主配置文件 | `config.py` | 无改动（通过 config.json 覆盖） |
| 快捷键数据类 | `util/client/shortcut/shortcut_config.py` | 扩展（新增 role 字段） |
| 客户端状态 | `util/client/state.py` | 扩展（新增悬浮窗事件接口） |
| 客户端启动 | `util/client/startup.py` | 修改（加载 config.json） |
| LLM 处理流程 | `util/llm/` | 修改（支持直接指定角色） |

**新增组件**:
| 组件 | 文件路径 | 说明 |
|------|----------|------|
| GUI 配置工具 | `edit_config_gui.py` | 主入口，用户双击启动 |
| GUI 模块 | `gui/` | 配置界面组件 |
| 配置管理器 | `gui/config_manager.py` | config.json 读写 |
| 悬浮窗 | `gui/status_overlay.py` | 录音/识别状态显示 |
| 配置数据 | `config.json` | 用户配置存储 |

---

### 技术选择

| 类别 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | tkinter + ttkbootstrap | 轻量、无大型依赖、现代外观 |
| 配置格式 | JSON | 标准库支持、结构化 |
| 快捷键捕获 | pynput | 已在项目中使用 |
| 状态通信 | queue.Queue | 线程安全、简单 |

---

### 依赖与风险

**新增依赖**:
```
ttkbootstrap>=1.10
```

**已有依赖**（无需新增）:
- tkinter（Python 标准库）
- pynput（已在 requirements-client.txt）
- json（Python 标准库）

**技术风险**:
| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| ttkbootstrap 在某些 Windows 版本样式异常 | 低 | 提供 fallback 到原生 ttk |
| 悬浮窗焦点抢占 | 中 | 使用 `-toolwindow` 属性，不抢焦点 |
| config.json 被手动修改导致格式错误 | 低 | 加载时验证，出错则使用默认值 |

---

## 2. 宪章检查 (Constitution Check)

- [x] **架构一致性**: 新增 GUI 模块独立于核心逻辑，通过配置文件解耦
- [x] **性能影响评估**: GUI 仅在配置时运行，不影响识别性能；悬浮窗使用独立线程
- [x] **安全性合规**: API Key 使用掩码显示，config.json 存储明文（用户本地文件）
- [x] **向后兼容**: 无 config.json 时仍可正常运行（使用 config.py 默认值）

---

## 3. 阶段规划

### Phase 0: 研究与决策 ✅

- [x] output: `research.md` - 技术选型决策记录
- [x] output: `data-model.md` - 数据实体定义
- [x] output: `contracts/api-contracts.md` - 内部 API 契约

---

### Phase 1: 基础设施

**1.1 配置管理模块**
- [ ] 创建 `gui/__init__.py`
- [ ] 创建 `gui/config_manager.py`
  - 实现 `load()`, `save()`, `get_default()`
  - 实现配置验证逻辑
- [ ] 创建 `config.json` 默认模板

**1.2 扩展快捷键数据类**
- [ ] 修改 `util/client/shortcut/shortcut_config.py`
  - 添加 `role: Optional[str] = None` 字段
  - 更新 `Shortcut.from_dict()` 方法

**1.3 配置加载集成**
- [ ] 修改 `util/client/startup.py`
  - 启动时加载 config.json（如存在）
  - 将 GUI 配置合并到 ServerConfig/ClientConfig

---

### Phase 2: GUI 配置界面

**2.1 主窗口框架**
- [ ] 创建 `edit_config_gui.py` 入口脚本
- [ ] 创建 `gui/main_window.py`
  - 实现 ttkbootstrap 主题初始化
  - 实现分区布局框架

**2.2 ASR 配置面板**
- [ ] 创建 `gui/panels/asr_panel.py`
  - 模型选择单选按钮组
  - GPU 设置复选框
  - 模型描述标签

**2.3 快捷键配置面板**
- [ ] 创建 `gui/panels/shortcut_panel.py`
  - 可编辑表格（Treeview）
  - 添加/删除按钮
  - 按键捕获对话框
  - 角色选择下拉框

**2.4 LLM 配置面板**
- [ ] 创建 `gui/panels/llm_panel.py`
  - 本地/云端切换
  - Ollama 模型下拉框（动态获取）
  - 云端 Provider 选择
  - API Key 输入（掩码）
  - 停止键选择

**2.5 悬浮窗配置面板**
- [ ] 创建 `gui/panels/overlay_panel.py`
  - 启用开关
  - 位置选择下拉框
  - 透明度滑块
  - 延迟时间输入

**2.6 底部操作区**
- [ ] 实现保存按钮逻辑
- [ ] 实现启动服务按钮
  - 启动 `start_server.py`
  - 启动 `start_client.py`

---

### Phase 3: 状态悬浮窗

**3.1 悬浮窗实现**
- [ ] 创建 `gui/status_overlay.py`
  - 无边框透明窗口
  - 状态图标和文字显示
  - 录音时长实时更新
  - 自动淡出动画

**3.2 状态通信集成**
- [ ] 修改 `util/client/state.py`
  - 添加悬浮窗事件接口
  - 添加状态变更回调

**3.3 快捷键触发集成**
- [ ] 修改 `util/client/shortcut/shortcut_manager.py`
  - 录音开始/结束时发送悬浮窗事件
  - 传递角色信息

---

### Phase 4: LLM 角色绑定

**4.1 角色传递机制**
- [ ] 修改 `util/llm/llm_role_loader.py`
  - 支持直接指定角色名（跳过前缀匹配）
  
**4.2 快捷键-角色联动**
- [ ] 修改识别完成后的处理逻辑
  - 如果触发快捷键有绑定角色，使用该角色
  - 否则走原有前缀匹配流程

---

### Phase 5: 测试与打磨

**5.1 功能测试**
- [ ] 配置保存/加载测试
- [ ] 快捷键捕获测试
- [ ] Ollama 模型列表获取测试
- [ ] 悬浮窗显示测试

**5.2 边界情况**
- [ ] config.json 不存在
- [ ] config.json 格式错误
- [ ] Ollama 未安装
- [ ] 快捷键重复

**5.3 用户体验优化**
- [ ] 添加工具提示（Tooltip）
- [ ] 添加快捷键说明
- [ ] 优化表格交互

---

## 4. 文件结构预览

```
CapsWriter-Offline/
├── edit_config_gui.py          # 🆕 GUI 入口
├── config.json                 # 🆕 用户配置（自动生成）
├── config.py                   # 现有（不修改）
├── gui/                        # 🆕 GUI 模块
│   ├── __init__.py
│   ├── main_window.py          # 主窗口
│   ├── config_manager.py       # 配置管理
│   ├── status_overlay.py       # 悬浮窗
│   ├── ollama_client.py        # Ollama 交互
│   ├── role_manager.py         # 角色管理
│   └── panels/                 # UI 面板
│       ├── __init__.py
│       ├── asr_panel.py
│       ├── shortcut_panel.py
│       ├── llm_panel.py
│       └── overlay_panel.py
├── util/
│   ├── client/
│   │   ├── shortcut/
│   │   │   └── shortcut_config.py  # 修改：添加 role 字段
│   │   ├── startup.py              # 修改：加载 config.json
│   │   └── state.py                # 修改：添加悬浮窗接口
│   └── llm/
│       └── llm_role_loader.py      # 修改：支持指定角色
└── requirements-client.txt     # 更新：添加 ttkbootstrap
```

---

## 5. 下一步

完成本计划后：
1. ~~运行 `/design`~~ (UI 已在契约中定义，无需额外设计)
2. 运行 `/speckit.tasks` 生成可执行任务列表
3. 运行 `/speckit.implement` 执行实现

---

## 附录：关键代码示例

### A1. config.json 加载逻辑

```python
# gui/config_manager.py
import json
from pathlib import Path
from config import ServerConfig, ClientConfig

CONFIG_FILE = Path('config.json')

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return get_default_config()
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return validate_and_fill_defaults(config)
    except json.JSONDecodeError:
        backup_and_reset()
        return get_default_config()

def apply_to_runtime(config: dict):
    """将配置应用到运行时"""
    # ASR
    ServerConfig.model_type = config['asr']['model_type']
    ServerConfig.vulkan_enable = config['asr']['vulkan_enable']
    ServerConfig.vulkan_force_fp32 = config['asr']['vulkan_force_fp32']
    
    # Shortcuts
    ClientConfig.shortcuts = config['shortcuts']
    
    # LLM
    ClientConfig.llm_enabled = config['llm']['enabled']
    ClientConfig.llm_stop_key = config['llm']['stop_key']
```

### A2. 悬浮窗核心实现

```python
# gui/status_overlay.py
import tkinter as tk
from tkinter import ttk

class StatusOverlay:
    def __init__(self, config):
        self.config = config
        self.root = None
        self._build_window()
    
    def _build_window(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self.config['opacity'])
        self.root.attributes('-toolwindow', True)
        
        # 位置计算
        self._position_window()
        
        # 内容
        self.label = ttk.Label(self.root, text="", font=('Microsoft YaHei', 14))
        self.label.pack(padx=20, pady=10)
        
        self.root.withdraw()  # 初始隐藏
    
    def show(self, status, role=None):
        icons = {'recording': '🎙️', 'recognizing': '⏳', 'done': '✅'}
        self.label.config(text=f"{icons.get(status, '')} {status}")
        self.root.deiconify()
    
    def hide(self, delay_ms=0):
        if delay_ms > 0:
            self.root.after(delay_ms, self.root.withdraw)
        else:
            self.root.withdraw()
```

### A3. 快捷键捕获

```python
# gui/shortcut_capture.py
from pynput import keyboard, mouse

class ShortcutCapture:
    def __init__(self, callback):
        self.callback = callback
        self.keyboard_listener = None
        self.mouse_listener = None
    
    def start(self):
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key)
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.keyboard_listener.start()
        self.mouse_listener.start()
    
    def _on_key(self, key):
        key_name = self._normalize_key(key)
        self.callback(key_name, 'keyboard')
        self.stop()
    
    def _on_click(self, x, y, button, pressed):
        if pressed and button in [mouse.Button.x1, mouse.Button.x2]:
            self.callback(button.name, 'mouse')
            self.stop()
    
    def stop(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
```
