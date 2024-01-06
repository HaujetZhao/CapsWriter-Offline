# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from rich import inspect
from pprint import pprint


from os.path import join, basename, dirname, exists
from os import walk, makedirs, sep
from shutil import copyfile, rmtree

# 初始化空列表
binaries = []
hiddenimports = []
datas = []

# 额外复制 dll
modules = ['onnxruntime']
for module in modules: 
    tmp_ret = collect_all(module)
    binaries += tmp_ret[1]


a_1 = Analysis(
    ['start_server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build_hook.py'],
    excludes=['IPython', 'PIL', 
              'PySide6', 'PySide2', 'PyQt5', 
              'matplotlib', 'wx', 
              'funasr', 'pydantic', 'torch', 
              ],
    noarchive=False,
)

a_2 = Analysis(
    ['start_client.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build_hook.py'],
    excludes=['IPython', 'PIL', 
              'PySide6', 'PySide2', 'PyQt5', 
              'matplotlib', 'wx', 
              ],
    noarchive=False,
)


# 排除不要打包的模块
private_module = ['util', 'config', 
                  'core_server', 
                  'core_client', 
                  ]
pure = a_1.pure.copy()
a_1.pure.clear()
for name, src, type in pure:
    condition = [name == m or name.startswith(m + '.') for m in private_module]
    if condition and any(condition):
        ...
    else:
        a_1.pure.append((name, src, type))    # 把需要保留打包的 py 文件重新添加回 a.pure

pure = a_2.pure.copy()
a_2.pure.clear()
for name, src, type in pure:
    condition = [name == m or name.startswith(m + '.') for m in private_module]
    if condition and any(condition):
        ...
    else:
        a_2.pure.append((name, src, type))    # 把需要保留打包的 py 文件重新添加回 a.pure


pyz_1 = PYZ(a_1.pure)
pyz_2 = PYZ(a_2.pure)


exe_1 = EXE(
    pyz_1,
    a_1.scripts,
    [],
    exclude_binaries=True,
    name='start_server',
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
    icon=['assets\\icon.ico'],
    contents_directory='internal',
)
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
    icon=['assets\\icon.ico'],
    contents_directory='internal',
)

coll = COLLECT(
    exe_1,
    a_1.binaries,
    a_1.datas,

    exe_2,
    a_2.binaries,
    a_2.datas,

    strip=False,
    upx=True,
    upx_exclude=[],
    name='CapsWriter-Offline',
)


# 复制额外所需的文件
my_files = ['config.py', 
            'core_server.py', 
            'core_client.py', 
            'hot-en.txt', 'hot-zh.txt', 'hot-rule.txt', 'keywords.txt', 
            'readme.md']
my_folders = ['assets', 'util']
dest_root = join('dist', basename(coll.name))
for folder in my_folders:
    for dirpath, dirnames, filenames in walk(folder):
        for filename in filenames:
            my_files.append(join(dirpath, filename))
for file in my_files:
    if not exists(file):
        continue
    dest_file = join(dest_root, file)
    dest_folder = dirname(dest_file)
    makedirs(dest_folder, exist_ok=True)
    copyfile(file, dest_file)


# 为 models 文件夹建立链接，免去复制大文件
from platform import system
from subprocess import run
if system() == 'Windows':
    link_folders = ['models', 'util']
    for folder in link_folders:
        if not exists(folder):
            continue
        dest_folder = join(dest_root, folder)
        if exists(dest_folder):
            rmtree(dest_folder)
        cmd = ['mklink', '/j', dest_folder, folder]
        run(cmd, shell=True)



