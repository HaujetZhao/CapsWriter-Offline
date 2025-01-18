# pyright: reportAttributeAccessIssue=false
# pyright: reportGeneralTypeIssues=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
import ctypes


def empty_working_set(pid: int) -> None:
    # 获取 pid 的句柄
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)

    # 清空工作集
    ctypes.windll.psapi.EmptyWorkingSet(handle)

    # 关闭进程句柄
    ctypes.windll.kernel32.CloseHandle(handle)


def empty_current_working_set() -> None:
    # 获取当前进程ID
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    empty_working_set(pid)
