# -*- mode: python ; coding: utf-8 -*-

# 初始化空列表
hiddenimports = [
    'pydantic', 
    'langchain.chains.conversation.base', 
    'pystray._base',
    'pystray._win32', 
    'pystray._xorg', 
    'pyautogui._pyautogui_x11'
]


a = Analysis(
    ['start_client_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('config.py', '.'), ('hot-en.txt', '.'), ('hot-zh.txt', '.'), ('hot-rule.txt', '.'), ('keywords.txt', '.')],
    hiddenimports = hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['IPython', 'PIL', 
              'PySide6', 'PySide2', 'PyQt5', 
              'matplotlib', 'wx', 
              ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='start_client_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\AiMaS.ico'],
    contents_directory='internal_client_gui',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='start_client_gui',
)
