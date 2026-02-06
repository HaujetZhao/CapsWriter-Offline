# -*- mode: python ; coding: utf-8 -*-
"""
现代化 PyInstaller 打包配置 - 仅客户端
适配 PyInstaller 6.0+ 版本

这是为了给 Win7 打包客户端而专设的
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
# from PyInstaller.building.build_main import Analysis, COLLECT
from os.path import join, basename, dirname, exists
from os import walk, makedirs
from shutil import copyfile, rmtree

# ==================== 打包配置选项 ====================

# 是否收集 CUDA provider（客户端通常不需要）
# - True: 包含 onnxruntime_providers_cuda.dll，支持 GPU 加速（需要在用户机器安装 CUDA 和 CUDNN）
# - False: 不包含 CUDA provider，只使用 CPU 模式（打包体积更小，兼容性更好）
INCLUDE_CUDA_PROVIDER = False

# ====================================================


# 初始化空列表
binaries = []
hiddenimports = []
datas = []

# 收集 sherpa_onnx 相关文件（客户端不需要，但保持一致性）
try:
    sherpa_datas = collect_data_files('sherpa_onnx', include_py_files=False)

    # 根据 INCLUDE_CUDA_PROVIDER 决定是否收集 CUDA provider
    if not INCLUDE_CUDA_PROVIDER:
        # 过滤掉 CUDA provider 文件
        filtered_datas = []
        for src, dest in sherpa_datas:
            # 检查是否是 CUDA provider 相关文件
            if 'providers_cuda' not in basename(src).lower():
                filtered_datas.append((src, dest))
            else:
                print(f"[INFO] 排除 CUDA provider: {basename(src)}")
        sherpa_datas = filtered_datas

    datas += sherpa_datas
except:
    pass

# 收集 Pillow 相关文件（用于托盘图标）
try:
    pillow_datas = collect_data_files('PIL', include_py_files=False)
    datas += pillow_datas
    pillow_binaries = collect_all('PIL')
    binaries += pillow_binaries[1]
except:
    pass

# 隐藏导入 - 确保所有需要的模块都被包含
hiddenimports += [
    'websockets',
    'websockets.client',
    'websockets.server',
    'rich',
    'rich.console',
    'rich.markdown',
    'keyboard',
    'pyclip',
    'numpy',
    'sounddevice',
    'pypinyin',
    'watchdog',
    'typer',
    'srt',
    'PIL',           # Pillow 用于托盘图标
    'PIL.Image',
    'pystray',       # 托盘图标库
]

a_2 = Analysis(
    ['start_client.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build_hook.py'],
    excludes=['IPython',
              'PySide6', 'PySide2', 'PyQt5',
              'matplotlib', 'wx',
              ],
    noarchive=False,
)

# 客户端过滤从系统 CUDA 目录收集的 DLL（保持一致性）
filtered_binaries = []
for name, src, type in a_2.binaries:
    src_lower = src.lower() if isinstance(src, str) else ''
    is_system_cuda_dll = (
        '\\nvidia gpu computing toolkit\\cuda\\' in src_lower or
        '\\nvidia\\cudnn\\' in src_lower or
        ('\\cuda\\v' in src_lower and '\\bin\\' in src_lower)
    )
    is_unwanted_onnx_dll = (
        'onnxruntime_providers_cuda.dll' in name.lower() or
        'directml.dll' in name.lower()
    )

    if not is_system_cuda_dll and not is_unwanted_onnx_dll:
        filtered_binaries.append((name, src, type))
    else:
        reason = "环境 CUDA DLL" if is_system_cuda_dll else "冗余 ONNX DLL"
        print(f"[INFO] 排除 {reason}: {name} (从 {src} 收集)")
a_2.binaries = filtered_binaries


# 排除不要打包的模块（这些将作为源文件复制）
private_module = ['util', 'config_client', 'config_server', 'LLM', 
                  'core_server',
                  'core_client',
                  ]

pure = a_2.pure.copy()
a_2.pure.clear()
for name, src, type in pure:
    condition = [name == m or name.startswith(m + '.') for m in private_module]
    if condition and any(condition):
        ...
    else:
        a_2.pure.append((name, src, type))


pyz_2 = PYZ(a_2.pure)


exe_2 = EXE(
    pyz_2,
    a_2.scripts,
    [],
    exclude_binaries=True,
    name='start_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\\\icon.ico'],
    # 所有第三方依赖放入 internal 目录
    contents_directory='internal',
)

coll = COLLECT(
    exe_2,
    a_2.binaries,
    a_2.datas,

    strip=False,
    upx=True,
    upx_exclude=[],
    name='CapsWriter-Offline-Client',
)


# 复制额外所需的文件（只复制用户自己写的文件）
my_files = [
    'config_client.py',
    'core_client.py',
    'hot.txt',
    'hot-server.txt',
    'hot-rule.txt',
    'hot-rectify.txt',
    'readme.md'
]
my_folders = []     # 使用软链接，不再复制
dest_root = join('dist', basename(coll.name))

# 复制文件夹中的文件
for folder in my_folders:
    if not exists(folder):
        continue
    for dirpath, dirnames, filenames in walk(folder):
        for filename in filenames:
            src_file = join(dirpath, filename)
            if exists(src_file):
                my_files.append(src_file)

# 执行文件复制到根目录（不是 internal）
for file in my_files:
    if not exists(file):
        continue
    # 保持相对路径结构
    rel_path = file.replace('\\', '/') if '\\' in file else file
    dest_file = join(dest_root, rel_path)
    dest_folder = dirname(dest_file)
    makedirs(dest_folder, exist_ok=True)
    copyfile(file, dest_file)


# 为 models 文件夹建立链接，免去复制大文件
from platform import system
from subprocess import run

if system() == 'Windows':
    link_folders = ['assets', 'util', 'LLM', 'log']
    for folder in link_folders:
        if not exists(folder):
            continue
        dest_folder = join(dest_root, folder)
        if exists(dest_folder):
            if os.path.islink(dest_folder) or os.path.isdir(dest_folder):
                try:
                    rmtree(dest_folder)
                except:
                    # 如果是 junction，rmtree 可能会失败，尝试调用 rmdir
                    run(['rmdir', '/s', '/q', dest_folder], shell=True)
        # 使用管理员权限运行的命令提示符来创建目录连接符
        cmd = ['mklink', '/j', dest_folder, folder]
        try:
            run(cmd, shell=True, check=True)
        except:
            print(f'警告：无法创建目录连接符 {dest_folder}，请手动创建或复制文件夹')
