# PyInstaller 打包指南

## 📦 新版本 PyInstaller 打包配置

### 目录结构设计

打包后的目录结构清晰分离：

```
dist/CapsWriter-Offline/
├── start_server.exe          # 服务端可执行文件
├── start_client.exe          # 客户端可执行文件
│
├── internal/                 # 第三方依赖（PyInstaller 自动生成）
│   ├── *.dll                 # 所有第三方 DLL 文件
│   ├── *.pyd                 # 所有第三方 PYD 文件
│   └── ...
│
├── config.py                 # 用户配置文件
├── core_server.py            # 服务端核心代码
├── core_client.py            # 客户端核心代码
│
├── util/                     # 工具模块（用户代码）
│   ├── __init__.py
│   ├── client/               # 客户端工具
│   ├── server/               # 服务端工具
│   ├── llm/                  # LLM 处理
│   ├── hotword/              # 热词管理
│   └── ...
│
├── LLM/                      # LLM 角色定义
│   ├── __init__.py
│   ├── default.py
│   ├── 翻译.py
│   ├── Python.py
│   └── ...
│
├── assets/                   # 资源文件
│   └── icon.ico
│
├── models/                   # 模型文件（目录连接符）
│   ├── FunASR-Nano/          # 轻量级模型（推荐）
│   ├── SenseVoice-Small/     # 多语言模型
│   ├── Paraformer/           # 大模型
│   ├── Punct-CT-Transformer/ # 标点模型
│   └── FireRed/              # 大模型（未使用）
│
├── hot.txt                   # 热词 - 基于 RAG 音素匹配（中英统一）
├── hot-rule.txt              # 正则表达式规则
└── readme.md
```

### 设计理念

1. **internal/** - 第三方依赖
   - 所有 DLL、PYD 文件
   - PyInstaller 自动管理
   - 用户不需要关心

2. **根目录** - 用户代码和配置
   - 只有你自己写的 Python 文件
   - 配置文件（*.txt）
   - 方便用户查看和修改

3. **models/** - 目录连接符
   - 链接到源代码的 models 文件夹
   - 避免复制大文件
   - 节省打包时间

## 🚀 打包命令

### 完整打包（服务端 + 客户端）

```bash
pyinstaller build.spec
```

### 仅打包客户端（用于 Win7）

```bash
pyinstaller build-client.spec
```

## 🔧 打包配置选项

在 [`build.spec`](../build.spec) 中可以配置以下选项：

### CUDA Provider 支持

```python
# 是否收集 CUDA provider
# - True: 包含 onnxruntime_providers_cuda.dll，支持 GPU 加速（需要在用户机器安装 CUDA 和 CUDNN）
# - False: 不包含 CUDA provider，只使用 CPU 模式（打包体积更小，兼容性更好）
INCLUDE_CUDA_PROVIDER = False
```

### 排除系统 CUDA DLL

打包配置会自动排除从系统 CUDA 安装目录收集的 DLL，避免冲突：
- `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v*\bin\`
- `C:\Program Files\NVIDIA\CUDNN\v*\bin\`

### 排除的用户模块

以下模块不会被打包进 exe，而是作为源文件复制到根目录：
- `util/` - 工具模块
- `config.py` - 配置文件
- `LLM/` - LLM 角色定义
- `core_*.py` - 核心源码入口

## 📝 推荐的打包流程

### 步骤 1：环境准备

```bash
# 激活 conda 环境
conda activate capswriter

# 安装 PyInstaller
pip install pyinstaller
```

### 步骤 2：安装依赖

```bash
# 安装服务端依赖（包含 Sherpa-ONNX）
pip install -r requirements-server.txt

# 安装客户端依赖
pip install -r requirements-client.txt
```

**依赖文件说明**:

**服务端依赖** ([`requirements-server.txt`](../requirements-server.txt)):
```text
# ASR 核心
-f https://k2-fsa.github.io/sherpa/onnx/cuda-cn.html
sherpa-onnx==1.12.20+cuda12.cudnn9
kaldi-native-fbank==1.17
numpy
typeguard==2.13.3

# 基础
rich
websockets

# 托盘与图像
pystray
Pillow
```

**客户端依赖** ([`requirements-client.txt`](../requirements-client.txt)):
```text
# 基础与 CLI
rich
typer
colorama

# 系统、输入与硬件
keyboard
pyclip
sounddevice
watchdog

# 网络与 API
websockets
openai
httpx

# 数据处理
numpy
numba
pypinyin
srt

# 托盘与图像
pystray
Pillow

# 打包
pyinstaller
```

### 步骤 3：清理旧的构建文件

```bash
# Windows
rmdir /s /q build dist

# Linux/Mac
rm -rf build dist
```

### 步骤 4：运行打包

```bash
# 完整打包（服务端 + 客户端）
pyinstaller build.spec

# 或者仅打包客户端（Win7 兼容需 Python3.8）
pyinstaller build-client.spec
```

**调试模式**（如果遇到问题）：
```bash
# 启用详细日志，查看哪些文件被打包了
pyinstaller --log-level DEBUG build.spec

# 只查看 WARNING 和 ERROR
pyinstaller --log-level WARN build.spec
```

### 步骤 5：验证目录结构

```bash
cd dist\CapsWriter-Offline

# 检查可执行文件
dir *.exe

# 检查 internal 目录
dir internal

# 检查用户文件
dir *.py
dir util
dir LLM
dir assets

# 检查 models 连接符
dir models
```

### 步骤 6：测试运行

```bash
# 测试服务端
start_server.exe

# 测试客户端
start_client.exe
```

**常见问题**:
- 如果缺少 DLL，检查 `internal/` 目录是否完整
- 如果找不到模型，检查 `models/` 连接符是否正确创建
- 如果热词不生效，检查 `hot*.txt` 文件是否存在

### 步骤 7：打包分发

```bash
# 使用 7-Zip 或其他工具压缩
# 注意：如果使用目录连接符，需要提醒接收方
# 或者直接复制 models/ 文件夹而不是创建连接符
```

## 🎯 打包最佳实践

### 1. 版本管理

在 [`config.py`](../config.py) 中定义版本号：
```python
__version__ = '2.3'
```

### 2. 模型管理

模型文件单独打包，用户下载后放入 `models/` 目录：
- FunASR-Nano（推荐）: 约 300MB
- SenseVoice: 约 500MB
- Paraformer: 约 1GB

### 3. 目录连接符

打包脚本会自动创建目录连接符（需要管理员权限）：
```python
link_folders = ['models', 'assets', 'util', 'LLM', '2026', 'logs']
```

如果创建失败，会提示用户手动复制文件夹。

### 4. 隐藏导入

打包配置包含所有必要的隐藏导入：
```python
hiddenimports = [
    'websockets', 'keyboard', 'pyclip', 'numpy',
    'sounddevice', 'pypinyin', 'watchdog', 'typer',
    'srt', 'sherpa_onnx', 'PIL', 'pystray',
    # ...
]
```

### 5. 排除模块

以下模块会被排除以减小体积：
```python
excludes = [
    'IPython', 'PySide6', 'PySide2', 'PyQt5',
    'matplotlib', 'wx', 'funasr', 'pydantic', 'torch',
]
```

## 📚 参考资源

### PyInstaller 文档
- [PyInstaller 6.0 Changelog](https://pyinstaller.org/en/v6.0.0/CHANGES.html)
- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [Spec File Format](https://pyinstaller.org/en/stable/spec-file.html)
- [PyInstaller Log Levels](https://pyinstaller.org/en/stable/advanced-features.html#logging)

### Sherpa-ONNX 文档
- [Sherpa-ONNX GitHub](https://github.com/k2-fsa/sherpa-onnx)
- [Sherpa-ONNX 文档](https://k2-fsa.github.io/sherpa/onnx/)

### 项目相关
- [CapsWriter-Offline README](../readme.md)
- [开发指南](../CLAUDE.md)

## 🔍 故障排查

### 常见问题

**1. 打包后运行报错 "ModuleNotFoundError"**
- 检查 `hiddenimports` 是否包含该模块
- 使用 `--log-level DEBUG` 查看打包日志

**2. 找不到 DLL 文件**
- 检查 `internal/` 目录是否包含所需的 DLL
- 检查 DLL 是否被错误排除

**3. 模型文件加载失败**
- 确认 `models/` 连接符创建成功
- 或手动复制模型文件到打包目录

**4. 热词不生效**
- 确认 `hot*.txt` 文件被复制到根目录
- 检查文件编码是否为 UTF-8

**5. 客户端无法连接服务端**
- 检查防火墙设置
- 确认端口 6016 未被占用


---

**更新日期**: 2026-01-13
**PyInstaller 版本**: 6.0+
**Python 版本**: 3.8+
**Sherpa-ONNX 版本**: 1.12.20
**项目版本**: CapsWriter-Offline v2.2
