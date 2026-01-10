# coding: utf-8
"""
异步线程执行工具

提供 asyncio.to_thread 的兼容实现（Python 3.8 中不存在）。
在异步上下文中安全地执行阻塞函数。
"""

import functools
import contextvars
from asyncio import events
from typing import Any, Callable, TypeVar

__all__ = ('to_thread',)

T = TypeVar('T')


async def to_thread(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """
    在单独的线程中异步运行函数
    
    将阻塞函数转换为协程，在线程池执行器中运行。
    当前的 contextvars.Context 会被传播到新线程。
    
    Args:
        func: 要执行的函数
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数
        
    Returns:
        函数的返回值
        
    Example:
        >>> result = await to_thread(blocking_io_function, arg1, arg2)
    """
    loop = events.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)
