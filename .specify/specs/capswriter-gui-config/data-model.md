# Data Model: CapsWriter-Offline GUI 配置工具

## 1. 配置数据模型

### 1.1 GUIConfig (主配置)

GUI 配置工具管理的完整配置结构，存储于 `config.json`。

```python
@dataclass
class GUIConfig:
    """GUI 配置工具管理的用户配置"""
    
    # 🆕 UI 主题：'light' | 'dark'
    theme: str = 'light'
    
    # ASR 模型配置
    asr: ASRConfig
    
    # 快捷键配置列表
    shortcuts: List[ShortcutConfig]
    
    # LLM 配置
    llm: LLMConfig
    
    # 状态悬浮窗配置
    overlay: OverlayConfig
    
    # 元信息
    version: str = "1.0"
    last_modified: str = ""  # ISO 8601 格式
```

---

### 1.2 ASRConfig (ASR 模型配置)

```python
@dataclass
class ASRConfig:
    """ASR 语音识别模型配置"""
    
    # 模型类型：'fun_asr_nano' | 'sensevoice' | 'paraformer'
    model_type: str = 'fun_asr_nano'
    
    # GPU 加速配置
    vulkan_enable: bool = True
    vulkan_force_fp32: bool = False
```

**验证规则**:
- `model_type` 必须是 `['fun_asr_nano', 'sensevoice', 'paraformer']` 之一
- `vulkan_force_fp32` 仅在 `vulkan_enable=True` 时有意义

**与现有系统映射**:
| GUI 字段 | config.py 字段 |
|----------|----------------|
| model_type | ServerConfig.model_type |
| vulkan_enable | ServerConfig.vulkan_enable |
| vulkan_force_fp32 | ServerConfig.vulkan_force_fp32 |

---

### 1.3 ShortcutConfig (快捷键配置)

```python
@dataclass
class ShortcutConfig:
    """单个快捷键配置"""
    
    # 按键标识符（如 'caps_lock', 'f1', 'x2'）
    key: str
    
    # 输入类型：'keyboard' | 'mouse'
    type: Literal['keyboard', 'mouse'] = 'keyboard'
    
    # 是否阻塞按键事件
    suppress: bool = False
    
    # 长按模式（True=长按录音，False=单击切换）
    hold_mode: bool = True
    
    # 触发阈值（秒），None 时使用全局默认值
    threshold: Optional[float] = None
    
    # 是否启用
    enabled: bool = True
    
    # 🆕 绑定的 LLM 角色（None=不绑定，使用语音前缀匹配）
    role: Optional[str] = None
```

**验证规则**:
- `key` 必须是有效的按键名称（参见 config.py 中的可用按键列表）
- `type='mouse'` 时，`key` 必须是 `['x1', 'x2']` 之一
- `threshold` 如果指定，应在 `[0.1, 2.0]` 范围内
- `role` 如果指定，必须是 `LLM/` 目录下存在的角色名（不含 .py 后缀）

**与现有系统映射**:
- 直接映射到 `ClientConfig.shortcuts` 列表中的字典
- `role` 字段为新增，需扩展 `Shortcut` 数据类

---

### 1.4 LLMConfig (LLM 配置)

```python
@dataclass
class LLMConfig:
    """LLM 大语言模型配置"""
    
    # 是否启用 LLM 功能
    enabled: bool = True
    
    # 中断输出的快捷键
    stop_key: str = 'esc'
    
    # 默认角色的 LLM 来源：'ollama' | 'cloud'
    default_source: Literal['ollama', 'cloud'] = 'ollama'
    
    # Ollama 本地模型配置
    ollama_model: str = 'gemma3:4b'
    
    # 云端 API 配置
    cloud_provider: str = 'deepseek'  # 'openai', 'deepseek', 'moonshot', 'zhipu', 'gemini', 'claude'
    cloud_api_key: str = ''  # 加密存储
    cloud_model: str = 'deepseek-chat'
```

**验证规则**:
- `stop_key` 必须是有效的按键名称
- `cloud_provider` 必须是支持的提供商之一
- `cloud_api_key` 不应以明文形式展示在 UI 中

**与现有系统映射**:
| GUI 字段 | 映射目标 |
|----------|----------|
| enabled | ClientConfig.llm_enabled |
| stop_key | ClientConfig.llm_stop_key |
| default_source, ollama_model | LLM/default.py 的 provider, model |
| cloud_* | LLM/default.py 的 provider, api_key, model |

**注意**: LLM 配置需要更新 `LLM/default.py` 文件中的对应字段。

---

### 1.5 OverlayConfig (状态悬浮窗配置)

```python
@dataclass
class OverlayConfig:
    """状态悬浮窗配置"""
    
    # 是否启用悬浮窗
    enabled: bool = True
    
    # 窗口位置：'center' | 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right'
    position: str = 'center'
    
    # 透明度 (0.0 - 1.0)
    opacity: float = 0.85
    
    # 完成后自动隐藏延迟（毫秒）
    auto_hide_delay: int = 1500
```

**验证规则**:
- `position` 必须是预定义值之一
- `opacity` 必须在 `[0.3, 1.0]` 范围内
- `auto_hide_delay` 必须在 `[500, 5000]` 范围内

---

## 2. 运行时状态模型

### 2.1 OverlayState (悬浮窗运行时状态)

```python
@dataclass
class OverlayState:
    """悬浮窗运行时状态（非持久化）"""
    
    # 当前状态：'idle' | 'recording' | 'recognizing' | 'done'
    status: str = 'idle'
    
    # 录音开始时间戳
    recording_start: float = 0.0
    
    # 录音时长（秒）
    recording_duration: float = 0.0
    
    # 识别结果预览
    result_preview: str = ''
    
    # 当前绑定的角色（如有）
    current_role: Optional[str] = None
```

**状态转换**:
```
idle ──(按下快捷键)──> recording ──(松开)──> recognizing ──(完成)──> done ──(延迟)──> idle
                         ↓                                           ↓
                    (短按取消)                                   (手动关闭)
                         ↓                                           ↓
                       idle                                        idle
```

---

## 3. 文件格式

### 3.1 config.json 示例

```json
{
  "version": "1.0",
  "last_modified": "2026-02-02T14:30:00+08:00",
  "theme": "light",
  "asr": {
    "model_type": "fun_asr_nano",
    "vulkan_enable": true,
    "vulkan_force_fp32": false
  },
  "shortcuts": [
    {
      "key": "caps_lock",
      "type": "keyboard",
      "suppress": true,
      "hold_mode": true,
      "enabled": true,
      "role": null
    },
    {
      "key": "f1",
      "type": "keyboard",
      "suppress": false,
      "hold_mode": true,
      "enabled": true,
      "role": "翻译"
    },
    {
      "key": "x2",
      "type": "mouse",
      "suppress": true,
      "hold_mode": true,
      "enabled": true,
      "role": null
    }
  ],
  "llm": {
    "enabled": true,
    "stop_key": "esc",
    "default_source": "ollama",
    "ollama_model": "gemma3:4b",
    "cloud_provider": "deepseek",
    "cloud_api_key": "",
    "cloud_model": "deepseek-chat"
  },
  "overlay": {
    "enabled": true,
    "position": "center",
    "opacity": 0.85,
    "auto_hide_delay": 1500
  }
}
```

---

## 4. 实体关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        GUIConfig                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                      config.json                     │    │
│  └─────────────────────────────────────────────────────┘    │
│         │              │              │            │         │
│         ▼              ▼              ▼            ▼         │
│   ┌─────────┐   ┌────────────┐  ┌─────────┐  ┌─────────┐    │
│   │ASRConfig│   │ShortcutList│  │LLMConfig│  │Overlay  │    │
│   │         │   │  [1..N]    │  │         │  │Config   │    │
│   └─────────┘   └────────────┘  └─────────┘  └─────────┘    │
│                        │                                     │
│                        ▼                                     │
│                 ┌────────────┐                               │
│                 │ShortcutItem│ ←── role (可选)               │
│                 │   key      │                               │
│                 │   type     │                               │
│                 │   enabled  │                               │
│                 └────────────┘                               │
└─────────────────────────────────────────────────────────────┘

                         ↓ 加载时覆盖

┌─────────────────────────────────────────────────────────────┐
│                   现有配置系统                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐     │
│  │ServerConfig │  │ ClientConfig │  │ LLM/default.py  │     │
│  │ (config.py) │  │  (config.py) │  │ (角色配置)       │     │
│  └─────────────┘  └──────────────┘  └─────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 数据验证模块

```python
# gui/validators.py

VALID_MODEL_TYPES = ['fun_asr_nano', 'sensevoice', 'paraformer']
VALID_KEY_TYPES = ['keyboard', 'mouse']
VALID_POSITIONS = ['center', 'top_left', 'top_right', 'bottom_left', 'bottom_right']
VALID_PROVIDERS = ['ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'gemini', 'claude']

def validate_config(config: dict) -> List[str]:
    """验证配置，返回错误列表"""
    errors = []
    
    # ASR 验证
    if config.get('asr', {}).get('model_type') not in VALID_MODEL_TYPES:
        errors.append(f"无效的 ASR 模型类型")
    
    # 快捷键验证
    for i, sc in enumerate(config.get('shortcuts', [])):
        if sc.get('type') not in VALID_KEY_TYPES:
            errors.append(f"快捷键 {i+1}: 无效的类型")
    
    # Overlay 验证
    opacity = config.get('overlay', {}).get('opacity', 0.85)
    if not (0.3 <= opacity <= 1.0):
        errors.append(f"透明度必须在 0.3 - 1.0 之间")
    
    return errors
```
