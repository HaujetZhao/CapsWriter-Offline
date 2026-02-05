# Contracts: CapsWriter-Offline GUI 配置工具

## 1. 内部模块契约

### 1.1 ConfigManager (配置管理器)

```python
class ConfigManager:
    """配置读写管理器"""
    
    CONFIG_FILE = Path('config.json')
    
    @classmethod
    def load(cls) -> dict:
        """
        加载配置
        
        Returns:
            完整配置字典，如果文件不存在则返回默认配置
        
        Raises:
            json.JSONDecodeError: 配置文件格式错误
        """
        pass
    
    @classmethod
    def save(cls, config: dict) -> None:
        """
        保存配置
        
        Args:
            config: 完整配置字典
        
        Raises:
            PermissionError: 无写入权限
            OSError: 其他文件系统错误
        """
        pass
    
    @classmethod
    def get_default(cls) -> dict:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        pass
    
    @classmethod
    def merge_to_runtime(cls, config: dict) -> None:
        """
        将配置合并到运行时配置类
        
        Args:
            config: 配置字典
            
        Effects:
            - 更新 ServerConfig 相关字段
            - 更新 ClientConfig 相关字段
        """
        pass
```

---

### 1.2 ShortcutCapture (快捷键捕获)

```python
class ShortcutCapture:
    """快捷键捕获工具"""
    
    def __init__(self, callback: Callable[[str, str], None]):
        """
        初始化捕获器
        
        Args:
            callback: 捕获到按键时的回调函数
                      参数: (key_name: str, key_type: 'keyboard'|'mouse')
        """
        pass
    
    def start(self) -> None:
        """开始监听，捕获下一个按键"""
        pass
    
    def stop(self) -> None:
        """停止监听"""
        pass
    
    def is_capturing(self) -> bool:
        """返回是否正在捕获"""
        pass
```

---

### 1.3 OllamaClient (Ollama 客户端)

```python
class OllamaClient:
    """Ollama 本地模型管理"""
    
    @staticmethod
    def list_models() -> List[str]:
        """
        获取已安装的 Ollama 模型列表
        
        Returns:
            模型名称列表，如 ['gemma3:4b', 'llama3.2:latest']
            如果 Ollama 未安装或无模型，返回空列表
        """
        pass
    
    @staticmethod
    def is_installed() -> bool:
        """
        检查 Ollama 是否已安装
        
        Returns:
            True 如果 ollama 命令可用
        """
        pass
    
    @staticmethod
    def is_running() -> bool:
        """
        检查 Ollama 服务是否运行
        
        Returns:
            True 如果 http://localhost:11434 可访问
        """
        pass
```

---

### 1.4 StatusOverlay (状态悬浮窗)

```python
class StatusOverlay:
    """状态悬浮窗控制器"""
    
    def __init__(self, config: OverlayConfig):
        """
        初始化悬浮窗
        
        Args:
            config: 悬浮窗配置
        """
        pass
    
    def show(self, status: str, role: Optional[str] = None) -> None:
        """
        显示悬浮窗
        
        Args:
            status: 状态类型 'recording' | 'recognizing' | 'done'
            role: 当前使用的角色名（可选）
        """
        pass
    
    def update_duration(self, duration: float) -> None:
        """
        更新录音时长显示
        
        Args:
            duration: 录音时长（秒）
        """
        pass
    
    def set_result(self, text: str) -> None:
        """
        设置识别结果预览
        
        Args:
            text: 识别结果文本
        """
        pass
    
    def hide(self, delay_ms: int = 0) -> None:
        """
        隐藏悬浮窗
        
        Args:
            delay_ms: 延迟毫秒数后隐藏
        """
        pass
    
    def is_visible(self) -> bool:
        """返回悬浮窗是否可见"""
        pass
```

---

### 1.5 RoleManager (角色管理器)

```python
class RoleManager:
    """LLM 角色管理"""
    
    LLM_DIR = Path('LLM')
    
    @classmethod
    def list_roles(cls) -> List[str]:
        """
        获取可用角色列表
        
        Returns:
            角色名称列表，如 ['default', '翻译', '大助理']
        """
        pass
    
    @classmethod
    def validate_role(cls, role_name: str) -> bool:
        """
        验证角色是否存在
        
        Args:
            role_name: 角色名称
        
        Returns:
            True 如果角色文件存在
        """
        pass
    
    @classmethod
    def get_role_description(cls, role_name: str) -> str:
        """
        获取角色描述
        
        Args:
            role_name: 角色名称
        
        Returns:
            角色描述文本（从文件中提取）
        """
        pass
```

---

## 2. 事件契约

### 2.1 状态事件

```python
# 状态事件类型
class StatusEvent:
    """悬浮窗状态更新事件"""
    
    type: Literal['recording_start', 'recording_update', 'recognizing', 'done', 'cancelled']
    
    # 录音相关
    duration: Optional[float] = None  # 录音时长
    
    # 识别相关
    result: Optional[str] = None  # 识别结果
    
    # 角色相关
    role: Optional[str] = None  # 当前角色

# 事件队列接口
event_queue: queue.Queue[StatusEvent]
```

---

## 3. UI 组件契约

### 3.1 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  CapsWriter-Offline 配置工具                          [X]   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🎙️ ASR 模型设置                                     │    │
│  │  ○ Fun-ASR-Nano (推荐，速度与精度平衡)              │    │
│  │  ○ SenseVoice (快速，适合实时)                      │    │
│  │  ○ Paraformer (高精度，适合离线转写)                │    │
│  │  ☐ 启用 Vulkan 加速   ☐ 强制 FP32                  │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ⌨️ 快捷键设置                                        │    │
│  │  ┌──────────┬────────┬────────┬────────┬────────┐   │    │
│  │  │ 按键     │ 类型   │ 模式   │ 角色   │ 启用   │   │    │
│  │  ├──────────┼────────┼────────┼────────┼────────┤   │    │
│  │  │ CapsLock │ 键盘   │ 长按   │ 无     │  ☑     │   │    │
│  │  │ F1       │ 键盘   │ 长按   │ 翻译   │  ☑     │   │    │
│  │  │ X2       │ 鼠标   │ 长按   │ 无     │  ☑     │   │    │
│  │  └──────────┴────────┴────────┴────────┴────────┘   │    │
│  │  [+ 添加]  [- 删除]                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🤖 LLM 设置                                          │    │
│  │  ○ 本地 Ollama      ○ 云端 API                      │    │
│  │  模型: [gemma3:4b ▼]  或  Provider: [DeepSeek ▼]    │    │
│  │                          API Key: [************]    │    │
│  │                          Model: [deepseek-chat   ]  │    │
│  │  中断键: [ESC ▼]                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 📊 状态悬浮窗                                        │    │
│  │  ☑ 启用状态显示                                     │    │
│  │  位置: [屏幕中央 ▼]  透明度: ━━━━━━━━●━━ 85%         │    │
│  │  自动隐藏延迟: [1.5] 秒                              │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│           [💾 保存配置]        [🚀 启动服务]                │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.2 快捷键捕获对话框

```
┌──────────────────────────────────────┐
│      请按下要绑定的快捷键...          │
│                                      │
│         [正在监听键盘/鼠标...]        │
│                                      │
│              [取消]                  │
└──────────────────────────────────────┘
```

---

### 3.3 悬浮窗状态显示

```
录音中:                    识别中:                    完成:
┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐
│  🎙️ 正在录音        │    │  ⏳ 正在识别...     │    │  ✅ 你好世界...     │
│     2.5s           │    │                    │    │                    │
└────────────────────┘    └────────────────────┘    └────────────────────┘
```

---

## 4. 错误处理契约

### 4.1 配置错误

| 错误类型 | 用户提示 | 处理方式 |
|----------|----------|----------|
| config.json 不存在 | (无提示，使用默认值) | 自动创建默认配置 |
| config.json 格式错误 | "配置文件格式错误，已重置为默认值" | 备份原文件，使用默认配置 |
| 权限错误 | "无法保存配置，请检查文件权限" | 显示错误对话框 |

### 4.2 运行时错误

| 错误类型 | 用户提示 | 处理方式 |
|----------|----------|----------|
| Ollama 未安装 | "未检测到 Ollama，请手动输入模型名称" | 显示手动输入框 |
| 服务端未启动 | "无法连接服务端，请先启动服务" | 显示错误对话框 |
| 快捷键冲突 | "快捷键已被占用：{key}" | 阻止添加 |
