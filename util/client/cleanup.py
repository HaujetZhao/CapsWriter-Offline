"""
客户端资源清理模块

负责在客户端退出时释放各种资源。
"""

import asyncio
from util.logger import get_logger
from util.common.lifecycle import lifecycle
from util.client.state import get_state, console

logger = get_logger('client')

def request_exit_from_tray(icon=None, item=None):
    """
    托盘引用的退出回调
    """
    logger.info("托盘退出: 用户点击退出菜单，准备清理资源并退出")
    lifecycle.request_shutdown(reason="Tray Icon")

def cleanup_client_resources():
    """
    清理客户端资源
    """
    state = get_state()
    
    # 停止快捷键监听
    if state.shortcut_handler:
        try:
            state.shortcut_handler.stop()
            logger.debug("快捷键监听已停止")
        except Exception as e:
            logger.warning(f"停止快捷键监听时发生错误: {e}")

    # 停止音频流
    if state.stream_manager:
        try:
            if hasattr(state.stream_manager, 'close'):
                 state.stream_manager.close()
            # state.stream will be set to None in state.reset() later
        except Exception as e:
            logger.warning(f"停止音频流时发生错误: {e}")

    # 停止结果处理器
    if state.processor:
        # processor 可能没有显式的 stop，主要依赖 loop 退出
        pass

    # 关闭 WebSocket 连接
    if state.websocket is not None:
        try:
            logger.debug("试图关闭 WebSocket 连接...")
            if state.loop and state.loop.is_running():
                # 使用 run_coroutine_threadsafe 确保在信号处理/多线程上下文中安全调度
                asyncio.run_coroutine_threadsafe(state.websocket.close(), state.loop)
            # 如果没有运行的 loop，websocket 将在状态 reset 时被清理
        except AttributeError:
             pass # 已经关闭或没有 closed 属性
        except Exception as e:
            logger.warning(f"关闭 WebSocket 连接时发生错误: {e}")
            
    # 彻底重置状态
    try:
        state.reset()
    except Exception as e:
        logger.warning(f"重置状态时发生错误: {e}")

    # 停止托盘图标
    try:
        from util.ui.tray import stop_tray
        stop_tray()
    except Exception as e:
        logger.warning(f"停止托盘图标时发生错误: {e}")

    logger.info("客户端资源清理完成")
    console.print('[green4]再见！')
