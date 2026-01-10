"""
Toast 模块日志配置

提供智能日志配置，既支持独立运行，也能集成到主程序。
"""
import logging
import sys


def get_toast_logger(name: str) -> logging.Logger:
    """
    获取 Toast 模块的日志记录器

    智能检测主程序是否已配置日志：
    - 如果主程序已配置（有 'client' 或 'server' logger），直接使用主程序的 logger
    - 如果主程序未配置，创建独立的 logger 输出到控制台

    Args:
        name: 日志记录器名称（通常是 __name__）

    Returns:
        配置好的日志记录器
    """
    # 检查主程序的 logger
    client_logger = logging.getLogger('client')
    server_logger = logging.getLogger('server')

    if client_logger.handlers:
        # 主程序（client）已配置，直接使用 client logger
        return client_logger
    elif server_logger.handlers:
        # 主程序（server）已配置，直接使用 server logger
        return server_logger
    else:
        # 独立运行，创建自己的 logger
        logger = logging.getLogger(name)

        # 如果还没有 handlers，添加控制台输出
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False  # 独立运行时不传播

        return logger


def configure_toast_logging(level: int = logging.DEBUG) -> None:
    """
    配置 Toast 模块的日志（独立运行时使用）

    Args:
        level: 日志级别
    """
    # 如果主程序已配置，不要覆盖
    client_logger = logging.getLogger('client')
    server_logger = logging.getLogger('server')
    if client_logger.handlers or server_logger.handlers:
        return

    # 配置根 logger
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
