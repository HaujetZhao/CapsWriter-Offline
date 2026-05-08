# coding: utf-8

import os
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler


class TruncatingFileHandler(RotatingFileHandler):
    """超过 maxBytes 后 truncate 文件，不保留任何备份文件"""

    _TAIL_LINES = 10  # truncate 前保留的末尾行数

    def doRollover(self):
        # truncate 前先读旧文件末尾几行
        tail = ''
        try:
            with open(self.baseFilename, 'r', encoding=self.encoding) as f:
                lines = f.readlines()
                tail = ''.join(lines[-self._TAIL_LINES:]).rstrip()
        except Exception:
            pass

        if self.stream:
            self.stream.close()
            self.stream = None
        # 用 'w' 模式重开，直接清空文件从头写
        self.stream = open(self.baseFilename, 'w', encoding=self.encoding)
        self.stream.write(f'--- Log truncated at {datetime.now()}\n')
        if tail:
            self.stream.write(f'--- Last {self._TAIL_LINES} lines of previous entries:\n{tail}\n\n')
        self.stream.flush()


class Logger:
    """日志系统管理器"""

    _loggers = {}

    @classmethod
    def setup(cls, name: str, log_dir: str = None, level: str = 'INFO', max_bytes: int = 10 * 1024 * 1024, log_filename: str = None):
        """
        设置并返回一个日志记录器

        Args:
            name: 日志记录器名称（通常是 'server' 或 'client'）
            log_dir: 日志文件目录，默认为项目根目录下的 logs 文件夹
            level: 日志级别，可选值：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
            max_bytes: 单个日志文件最大大小，默认 10MB
            backup_count: 保留的日志文件数量，默认 5 个
            log_filename: 自定义日志文件名前缀，如果不填则默认使用 name 或 'root'

        Returns:
            logging.Logger: 配置好的日志记录器
        """
        # 设置日志级别
        file_log_level = getattr(logging, level.upper(), logging.INFO)
        console_log_level = logging.WARNING  # 控制台强制只打印 WARNING 及以上

        # 如果已经初始化过，更新级别并返回
        if name in cls._loggers:
            logger = cls._loggers[name]
            logger.setLevel(min(file_log_level, console_log_level))
            for handler in logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    handler.setLevel(file_log_level)
                elif isinstance(handler, logging.StreamHandler):
                    handler.setLevel(console_log_level)
            return logger

        # 创建日志记录器
        logger = logging.getLogger(name if name else None)
        logger.setLevel(min(file_log_level, console_log_level))

        # 确保不会传播到 root logger
        if name:
            logger.propagate = False

        # 确定日志目录
        if log_dir is None:
            from config_client import BASE_DIR
            log_dir = os.path.join(BASE_DIR, 'logs')

        # 创建日志目录
        Path(log_dir).mkdir(parents=True, exist_ok=True)


        # 1. 文件处理器（根据传入 level 记录）
        file_name_prefix = log_filename or name or 'root'
        log_file = os.path.join(log_dir, f'{file_name_prefix}_latest.log')
        formatter = logging.Formatter(
            fmt='%(asctime)s.%(msecs)03d %(levelname)-5s [%(filename)20s:%(lineno)-3d] %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler = TruncatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            encoding='utf-8'
        )
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 2. 控制台处理器（固定 WARNING 及以上，使用 rich 渲染）
        stream_handler = RichHandler(
            level=console_log_level,
            rich_tracebacks=True,
            markup=True,
            show_path=False
        )
        logger.addHandler(stream_handler)

        # 缓存日志记录器
        cls._loggers[name] = logger

        return logger

    @classmethod
    def get_logger(cls, name: str):
        """
        获取已创建的日志记录器，如果不存在则创建一个默认的

        Args:
            name: 日志记录器名称

        Returns:
            logging.Logger: 日志记录器
        """
        if name not in cls._loggers:
            # 如果 logger 还没有被初始化，先创建一个默认的（INFO 级别）
            # 之后 core_client.py/core_server.py 会用正确的级别重新初始化
            return cls.setup(name, level='INFO')
        return cls._loggers[name]


# 便捷函数
def setup_logger(name: str, log_dir: str = None, level: str = 'INFO', **kwargs):
    """设置日志记录器的便捷函数"""
    return Logger.setup(name, log_dir, level, **kwargs)


def get_logger(name: str):
    """获取日志记录器的便捷函数"""
    return Logger.get_logger(name)
