# coding: utf-8
"""
Windows 内存管理工具

提供清空进程工作集的功能，用于释放物理内存。
仅在 Windows 平台有效。
"""

import ctypes
from typing import Optional


def empty_working_set(pid: int) -> None:
    """
    清空指定进程的物理内存工作集
    
    通过 Windows API 释放进程占用的物理内存，
    将其移至页面文件，减少内存占用。
    
    Args:
        pid: 进程 ID
        
    Note:
        仅在 Windows 平台有效，其他平台调用会失败。
    """
    # 获取进程句柄（PROCESS_ALL_ACCESS = 0x1F0FFF）
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
    
    if handle:
        # 清空工作集
        ctypes.windll.psapi.EmptyWorkingSet(handle)
        
        # 关闭进程句柄
        ctypes.windll.kernel32.CloseHandle(handle)


def empty_current_working_set() -> None:
    """
    清空当前进程的物理内存工作集
    
    获取当前进程 ID 并清空其工作集。
    通常在程序初始化完成后调用，释放初始化阶段占用的内存。
    """
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    empty_working_set(pid)