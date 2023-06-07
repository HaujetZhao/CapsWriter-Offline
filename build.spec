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
my_folders = ['assets', 'models']
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
    ['start_server.py'],
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

a2 = Analysis(
    ['start_client.py'],
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
temp = a.datas.copy(); a.datas.clear()
for dst, src, type in temp:
    c1 =  (dst == 'base_library.zip')
    c2 = any([dst.startswith(f) for f in my_folders])
    c3 = any([dst.startswith(f) for f in my_files])
    if any([c1, c2, c3]):
        a.datas.append((dst, src, type))
    else:
        a.datas.append((path.join('libs', dst), src, type))


temp = a2.datas.copy(); a2.datas.clear()
for dst, src, type in temp:
    c1 =  (dst == 'base_library.zip')
    c2 = any([dst.startswith(f) for f in my_folders])
    c3 = any([dst.startswith(f) for f in my_files])
    if any([c1, c2, c3]):
        a2.datas.append((dst, src, type))
    else:
        a2.datas.append((path.join('libs', dst), src, type))




# 把 a.binaries 中的二进制文件放到 a.datas ，作为普通文件复制到 libs 目录
for dst, src, type in a.binaries:
    c1 = (dst=='Python')                       # 不修改 Pyhton 
    c2 = re.fullmatch(r'python\d+\.dll', dst)  # 不修改 python310.dll
    if any([c1, c2]):
        a.datas.append((dst, src, 'DATA'))
    else:
        a.datas.append((path.join('libs', dst), src, 'DATA'))
a.binaries.clear()


for dst, src, type in a2.binaries:
    c1 = (dst=='Python')                       # 不修改 Pyhton 
    c2 = re.fullmatch(r'python\d+\.dll', dst)  # 不修改 python310.dll
    if any([c1, c2]):
        a2.datas.append((dst, src, 'DATA'))
    else:
        a2.datas.append((path.join('libs', dst), src, 'DATA'))
a2.binaries.clear()



# 把所有的 py 文件依赖用 a.datas 复制到 libs 文件夹
for name, src, type in a.pure:
    name = name.replace('.', os.sep)
    init = path.join(name, '__init__.py')
    pos = src.find(init) if init in src else src.find(name)
    dst = src[pos:]
    dst = path.join('libs', dst)
    a.datas.append((dst, src, 'DATA'))
a.pure.clear()

for name, src, type in a2.pure:
    name = name.replace('.', os.sep)
    init = path.join(name, '__init__.py')
    pos = src.find(init) if init in src else src.find(name)
    dst = src[pos:]
    dst = path.join('libs', dst)
    a2.datas.append((dst, src, 'DATA'))
a2.pure.clear()


# =============================================================================



pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz2 = PYZ(a2.pure, a2.zipped_data, cipher=block_cipher)


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
    pyz2,
    a2.scripts,
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
)



coll = COLLECT(
    exe,
    exe2,
    a.binaries,
    a.zipfiles,
    a.datas,
    a2.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CapsWriter-Offline',
)
