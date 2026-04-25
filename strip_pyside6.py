#!/usr/bin/env python3
"""
裁剪 PySide6 到最小集：QtCore + QtGui + QtWidgets + X11 平台插件
用于 --with-tray 构建模式，将裁剪后的 PySide6 注入 dist/internal/

用法: python strip_pyside6.py <target_dir>
  target_dir: dist/CapsWriter-Offline/internal
"""

import os
import shutil
import sys


KEEP_MODULES = {'QtCore', 'QtGui', 'QtWidgets'}

KEEP_QT_LIBS = {
    'libQt6Core.so.6',
    'libQt6Gui.so.6',
    'libQt6Widgets.so.6',
    'libQt6XcbQpa.so.6',
    'libQt6DBus.so.6',
    'libQt6OpenGL.so.6',
    'libQt6Svg.so.6',
}

KEEP_QT_LIB_PREFIXES = [
    'libQt6Core', 'libQt6Gui', 'libQt6Widgets',
    'libQt6XcbQpa', 'libQt6DBus', 'libQt6OpenGL', 'libQt6Svg',
]

KEEP_PLUGIN_DIRS = {'platforms', 'imageformats', 'iconengines'}

KEEP_TOP_FILES = {
    '__init__.py', '_config.py', '_git_pyside_version.py',
    'PySide6_Essentials.json',
}

KEEP_TOP_DIRS = {
    'support',
}


def matches_prefix(filename, prefixes):
    return any(filename.startswith(p) for p in prefixes)


def strip_pyside6(src_root, dst_root):
    pyside6_src = os.path.join(src_root, 'PySide6')
    shiboken6_src = os.path.join(src_root, 'shiboken6')

    if not os.path.isdir(pyside6_src):
        print(f"ERROR: {pyside6_src} not found")
        sys.exit(1)

    total_before = 0
    total_after = 0

    for dp, dn, fns in os.walk(pyside6_src):
        for f in fns:
            total_before += os.path.getsize(os.path.join(dp, f))

    # --- PySide6 ---
    dst_pyside6 = os.path.join(dst_root, 'PySide6')

    # Copy only needed .abi3.so + .pyi
    for mod in KEEP_MODULES:
        for ext in ['.abi3.so', '.pyi']:
            src = os.path.join(pyside6_src, f'{mod}{ext}')
            if os.path.isfile(src):
                os.makedirs(dst_pyside6, exist_ok=True)
                shutil.copy2(src, os.path.join(dst_pyside6, f'{mod}{ext}'))
                print(f'  + {mod}{ext}')

    # Copy libpyside (e.g. libpyside6.abi3.so.6.11)
    for f in os.listdir(pyside6_src):
        if f.startswith('libpyside6') and '.so' in f:
            shutil.copy2(os.path.join(pyside6_src, f), os.path.join(dst_pyside6, f))
            print(f'  + {f}')

    # Copy top-level files
    for f in os.listdir(pyside6_src):
        if f in KEEP_TOP_FILES and os.path.isfile(os.path.join(pyside6_src, f)):
            shutil.copy2(os.path.join(pyside6_src, f), os.path.join(dst_pyside6, f))
            print(f'  + {f}')

    # Copy top-level dirs
    for d in KEEP_TOP_DIRS:
        src_d = os.path.join(pyside6_src, d)
        if os.path.isdir(src_d):
            shutil.copytree(src_d, os.path.join(dst_pyside6, d))
            print(f'  + {d}/')

    # Copy Qt libs (only needed ones)
    qt_lib_src = os.path.join(pyside6_src, 'Qt', 'lib')
    qt_lib_dst = os.path.join(dst_pyside6, 'Qt', 'lib')
    if os.path.isdir(qt_lib_src):
        for f in os.listdir(qt_lib_src):
            if matches_prefix(f, KEEP_QT_LIB_PREFIXES):
                os.makedirs(qt_lib_dst, exist_ok=True)
                shutil.copy2(os.path.join(qt_lib_src, f), os.path.join(qt_lib_dst, f))
                print(f'  + Qt/lib/{f}')

    # Copy ICU (QtGui needs it)
    for f in os.listdir(qt_lib_src):
        if f.startswith('libicu'):
            os.makedirs(qt_lib_dst, exist_ok=True)
            shutil.copy2(os.path.join(qt_lib_src, f), os.path.join(qt_lib_dst, f))
            print(f'  + Qt/lib/{f}')

    # Copy plugins (only needed dirs)
    qt_plugins_src = os.path.join(pyside6_src, 'Qt', 'plugins')
    qt_plugins_dst = os.path.join(dst_pyside6, 'Qt', 'plugins')
    if os.path.isdir(qt_plugins_src):
        for pd in KEEP_PLUGIN_DIRS:
            src_pd = os.path.join(qt_plugins_src, pd)
            if os.path.isdir(src_pd):
                shutil.copytree(src_pd, os.path.join(qt_plugins_dst, pd))
                count = sum(len(fns) for _, _, fns in os.walk(src_pd))
                print(f'  + Qt/plugins/{pd}/ ({count} files)')

    # Copy qt.conf if exists
    qt_conf = os.path.join(pyside6_src, 'Qt', 'qt.conf')
    if os.path.isfile(qt_conf):
        os.makedirs(os.path.join(dst_pyside6, 'Qt'), exist_ok=True)
        shutil.copy2(qt_conf, os.path.join(dst_pyside6, 'Qt', 'qt.conf'))

    # --- shiboken6 ---
    if os.path.isdir(shiboken6_src):
        dst_shiboken6 = os.path.join(dst_root, 'shiboken6')
        shutil.copytree(shiboken6_src, dst_shiboken6)
        print(f'  + shiboken6/')

    # Calculate after size
    for dp, dn, fns in os.walk(dst_pyside6):
        for f in fns:
            total_after += os.path.getsize(os.path.join(dp, f))

    before_mb = total_before / 1024 / 1024
    after_mb = total_after / 1024 / 1024
    print(f'\nPySide6: {before_mb:.0f}MB → {after_mb:.0f}MB (stripped {before_mb - after_mb:.0f}MB)')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <target_internal_dir>")
        sys.exit(1)

    target = sys.argv[1]
    src = os.path.join(os.path.dirname(__file__), '.venv', 'lib', 'python3.12', 'site-packages')
    if not os.path.isdir(src):
        print(f"ERROR: site-packages not found at {src}")
        sys.exit(1)

    print(f"Stripping PySide6 → {target}")
    strip_pyside6(src, target)
