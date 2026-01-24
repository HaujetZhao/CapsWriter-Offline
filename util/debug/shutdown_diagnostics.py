
import sys
import traceback
import threading
import asyncio
from . import logger


def dump_active_stacks():
    """
    打印所有活跃线程和 Asyncio 任务的堆栈信息
    用于诊断程序无法退出、死锁等问题
    """
    logger.warning("=" * 20 + " 活跃线程堆栈转储 " + "=" * 20)
    
    # 1. 转储线程堆栈
    frames = sys._current_frames()
    for thread_id, frame in frames.items():
        thread = threading.enumerate()
        thread_name = "Unknown"
        is_daemon = False
        for t in thread:
            if t.ident == thread_id:
                thread_name = t.name
                is_daemon = t.daemon
                break
        
        logger.warning(f"Thread ID: {thread_id}, Name: {thread_name}, Daemon: {is_daemon}")
        stack = "".join(traceback.format_stack(frame))
        logger.warning(f"\n{stack}")

    logger.warning("=" * 20 + " Asyncio 任务堆栈转储 " + "=" * 20)

    # 2. 转储 Asyncio 任务
    try:
        loop = asyncio.get_running_loop()
        tasks = asyncio.all_tasks(loop)
        
        if not tasks:
            logger.warning("无活跃 Asyncio 任务")
        
        for task in tasks:
            name = task.get_name()
            coro = task.get_coro()
            logger.warning(f"Task: {name}, Coroutine: {coro}")
            
            # 获取协程的堆栈
            # 注意：这是协程当前的挂起点
            try:
                # 打印任务的 repr，通常包含当前等待的 future
                logger.warning(f"State: {task}")
                # Python 3.8+ 可以尝试直接打印 stack
                try:
                    stack = task.get_stack()
                    if stack:
                        logger.warning("Stack:")
                        for frame in stack:
                            logger.warning(f"  File {frame.f_code.co_filename}, line {frame.f_lineno}, in {frame.f_code.co_name}")
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"获取任务堆栈失败: {e}")
            logger.warning("-" * 30)
            
    except RuntimeError:
        logger.warning("无法获取运行中的事件循环")
    except Exception as e:
        logger.warning(f"转储 Asyncio 任务失败: {e}")

    logger.warning("=" * 50)
