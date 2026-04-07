# coding: utf-8
from . import logger
from pathlib import Path
from config_client import ClientConfig as Config
from ..hotword import get_hotword_manager
from ..llm.llm_handler import init_llm_system


class ResourceManager:
    """
    资源管理器：负责客户端公共资源（热词、LLM）的初始化与管理。
    """
    def __init__(self, state):
        self.state = state

    def initialize(self):
        """初始化所有公共资源"""
        self._setup_hotwords()
        self._setup_llm()

    def _setup_hotwords(self):
        """加载热词并启动监控"""
        logger.info("正在加载热词...")
        hotword_files = {
            'hot': Path('hot.txt'),
            'rule': Path('hot-rule.txt'),
            'rectify': Path('hot-rectify.txt'),
        }
        hotword_manager = get_hotword_manager(
            hotword_files=hotword_files,
            threshold=Config.hot_thresh,
            similar_threshold=Config.hot_similar,
            rectify_threshold=Config.hot_rectify
        )
        hotword_manager.load_all()
        hotword_manager.start_file_watcher()

    def _setup_llm(self):
        """初始化 LLM 系统对外接口"""
        logger.info("正在初始化 LLM 系统...")
        init_llm_system()
        logger.info("LLM 系统初始化完成")
