# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


# =============================================================================

from importlib.util import find_spec
from os.path import dirname
from os import sep
from copy import deepcopy
from pprint import pprint
import rich
import re
import os

# 空列表，用于准备要复制的数据
datas = []

# 文件夹依赖库
manual_modules = ['lazy_loader', 'numpy', 'librosa', 'onnxruntime', '_sounddevice_data']
for m in manual_modules:
    if not find_spec(m): continue
    p1 = dirname(find_spec(m).origin)
    p2 = 'libs' + sep + m
    datas.append((p1, p2))

# 单文件依赖库
datas.append((find_spec('sounddevice').origin, 'libs'))
datas.append((find_spec('_sounddevice').origin, 'libs'))
datas.append((find_spec('_cffi_backend').origin, 'libs'))

# 自定义文件
custom_file = ['core_client.py', 'core_server.py', 
               'hot-en.txt', 'hot-rule.txt', 'hot-zh.txt', 'keywords.txt', 
               'readme.md', ]
datas.append(('models/请将语音和标点模型放到此文件夹', 'models'))

# 自定义文件夹
custom_folder = ['util', 'assets']
for f in custom_file:
    datas.append((f, '.'))
for f in custom_folder:
    datas.append((f, f))

# =============================================================================







a = Analysis(
    ['start_server.py', 'start_client.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build_hook.py'],
    excludes=['numpy', 'librosa', 'onnxruntime', 'sounddevice'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)








# =============================================================================

# 把依赖包重定向到 libs 文件夹
def new_dest(package: str):
    if package == 'base_library.zip' or re.match(r'python\d+.dll', package):
        return package
    return 'libs' + os.sep + package
a.binaries = [(new_dest(x[0]), x[1], x[2]) for x in a.binaries]

# 将需要排除打包到 exe 的 py 模块
my_modules = ['core_client', 'core_server', 'util', 
              'util.chinese_itn', 
              'util.hot_sub_en', 
              'util.hot_sub_zh', 
              'util.hot_sub_rule']
# 将不需要打包的 py 模块删除
a.pure = [x for x in a.pure if x[0] not in my_modules]


# 删除自动添加的多余文件
trash = ['dist-info']
def filter_trash(name):
    for t in trash:
        if t not in name: continue
        print(f'\nfiltered: {name}\n')
        return False
    return True
a.datas = [x for x in a.datas if filter_trash(x[0]) ]

# =============================================================================





pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)



exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=False,
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
)

exe2 = EXE(
    pyz,
    a.scripts[:-2] + a.scripts[-1:],    # 提供给 a 的文件有两个，生成 scripts 列表后，依次执行，所以要把倒数第2个（即 start_server）删掉
    [],
    exclude_binaries=False,
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
)



coll = COLLECT(
    exe,
    exe2,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CapsWriter-Offline',
)
