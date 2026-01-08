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
│   ├── client_*.py
│   └── server_*.py
│
├── assets/                   # 资源文件
│   └── icon.ico
│
├── models/                   # 模型文件（目录连接符）
│   ├── Paraformer/
│   ├── SenseVoice-Small/
│   ├── FunASR-nano/
│   └── Punct-CT-Transformer/
│
├── hot-en.txt                # 英文热词
├── hot-zh.txt                # 中文热词
├── hot-rule.txt              # 规则热词
├── keywords.txt              # 关键词
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

## 📝 推荐的打包流程

### 步骤 1：清理旧的构建文件

```bash
rmdir /s /q build dist
```

### 步骤 2：安装依赖

```bash
pip install -r requirements-server.txt
pip install -r requirements-client.txt
```

### 步骤 3：运行打包

```bash
pyinstaller build.spec
```

**调试模式**（如果遇到问题）：
```bash
# 启用详细日志，查看哪些文件被打包了
pyinstaller --log-level DEBUG build.spec

# 只查看 WARNING 和 ERROR
pyinstaller --log-level WARN build.spec
```

### 步骤 4：验证目录结构

```bash
cd dist\CapsWriter-Offline

# 检查可执行文件
dir *.exe

# 检查 internal 目录
dir internal

# 检查用户文件
dir *.py
dir util
dir assets

# 检查 models 连接符
dir models
```

### 步骤 5：测试运行

```bash
# 测试服务端
start_server.exe

# 测试客户端
start_client.exe
```

### 步骤 6：打包分发

```bash
# 使用 7-Zip 或其他工具压缩
# 注意：如果使用目录连接符，需要提醒接收方
# 或者直接复制 models/ 文件夹而不是创建连接符
```

## 📚 参考资源

- [PyInstaller 6.0 Changelog](https://pyinstaller.org/en/v6.0.0/CHANGES.html)
- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [Spec File Format](https://pyinstaller.org/en/stable/spec-file.html)
- [PyInstaller Log Levels](https://pyinstaller.org/en/stable/advanced-features.html#logging)

---

**更新日期**: 2026-01-08
**PyInstaller 版本**: 6.0+
**Python 版本**: 3.8+
**项目版本**: CapsWriter-Offline v2.0
