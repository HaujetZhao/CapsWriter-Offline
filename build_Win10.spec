# -*- mode: python ; coding: utf-8 -*-


block_cipher = None



from importlib.util import find_spec
from os.path import dirname
from os import sep, path
from copy import deepcopy
from pathlib import Path
from pprint import pprint
import rich
import re
import os


#============================手动添加额外要复制的文件=====================================

# 空列表，用于准备要复制的数据
datas = []

# 这是要额外复制的模块
manual_modules = ['numpy', 'librosa', 'lazy_loader', 'onnxruntime']
for m in manual_modules:
    if not find_spec(m): continue
    p1 = dirname(find_spec(m).origin)
    p2 = m
    datas.append((p1, p2))

# 这是要额外复制的文件夹
my_folders = ['assets', 'util', 'models']
for f in my_folders:
    datas.append((f, f))

# 这是要额外复制的文件
my_files = ['hot-en.txt', 'hot-zh.txt', 'keywords.txt', 'hot-rule.txt', 
            'readme.md', 
            'core_server.py', 'core_client.py']
for f in my_files:
    datas.append((f, '.'))

#===============================================================================


a = Analysis(
    ['start_server.py', 'start_client.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build_hook.py'],
    excludes=['numpy', 'librosa'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)



#============================重定向二进制、py文件===================================================

# 把 a.datas 中不属于自定义的文件重定向到 libs 文件夹
temp, a.datas = a.datas, []
for d in temp:
    c1 =  (d[0] == 'base_library.zip')
    c2 = any([d[0].startswith(f) for f in my_folders])
    c3 = any([d[0].startswith(f) for f in my_files])
    if any([c1, c2, c3]):
        a.datas.append(d)
    else:
        a.datas.append((path.join('libs', d[0]), d[1], d[2]))


# 把 a.binaries 中的二进制文件放到 a.datas ，作为普通文件复制到 libs 目录
for b in a.binaries:
    c1 = (b[0]=='Python')                       # 不修改 Pyhton 
    c2 = re.fullmatch(r'python\d+\.dll', b[0])  # 不修改 python310.dll
    if any([c1, c2]):
        a.datas.append((b[0], b[1], 'DATA'))
    else:
        a.datas.append((path.join('libs', b[0]), b[1], 'DATA'))
a.binaries.clear()



# 把所有不是自定义模块的 py 文件用 a.datas 复制到 libs 文件夹
my_modules = ['core_client', 'core_server', 'util']
for py in a.pure:
    if any([re.match(m, py[0]) for m in my_modules]): continue
    pos = py[1].find(py[0].replace('.', sep))
    d0 = py[1][pos:]
    d1 = py[1]
    d2 = 'DATA'
    a.datas.append((path.join('libs', d0), d1, d2))
a.pure.clear()


# =============================================================================



pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
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
)

exe2 = EXE(
    pyz,
    a.scripts[:-2] + a.scripts[-1:],    # 提供给 a 的 py 脚本文件有两个，生成 scripts 列表后，依次执行，所以要把倒数第2个（即 start_server）删掉
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
