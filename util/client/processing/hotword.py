# coding: utf-8
"""
热词管理模块

提供 HotwordManager 类用于管理热词的加载、替换和文件监视。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Dict, Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from util.client.state import console
from util.hotword import corrector_rule as hot_sub_rule
from util.hotword.corrector_phoneme import PhonemeCorrector
from config import ClientConfig as Config
from util.logger import get_logger

# 日志记录器
logger = get_logger('client')

# 热词文件路径
HOTWORD_FILES = {
    'hot': Path('hot.txt'),
    'rule': Path('hot-rule.txt'),
}


class HotwordManager:
    """
    热词管理器
    
    负责热词的加载、替换和动态更新。
    使用统一的 hot.txt 进行 RAG 音素匹配。
    """
    
    def __init__(self):
        """初始化热词管理器"""
        self._observer: Optional[Observer] = None
        # 使用配置中的阈值初始化拼音纠错器
        self.corrector = PhonemeCorrector(threshold=Config.hot_rag_threshold)
    
    def load_all(self) -> None:
        """加载所有热词文件"""
        logger.info("正在加载热词...")
        self._load_hot()
        self._load_rule()
        console.line()
        logger.info("热词加载完成")
    
    def _load_hot(self) -> None:
        """加载热词（统一文件）"""
        path = HOTWORD_FILES['hot']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此放置热词，每行一个，井号开头为注释\n')
        
        with open(path, 'r', encoding='utf-8') as f:
            num = self.corrector.update_hotwords(f.read())
            
        console.print(f'已载入 [green4]{num:5}[/] 条热词')
        logger.debug(f"载入 {num} 条热词")
    
    def _load_rule(self) -> None:
        """加载自定义规则"""
        path = HOTWORD_FILES['rule']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置自定义规则\n毫安时 = mAh\n赫兹 = Hz')
        
        with open(path, 'r', encoding='utf-8') as f:
            num = hot_sub_rule.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num:5}[/] 条自定义替换规则')
        logger.debug(f"载入 {num} 条自定义替换规则")
    
    def substitute(self, text: str) -> str:
        """
        执行热词替换
        
        Args:
            text: 原始文本
            
        Returns:
            替换后的文本
        """
        # 1. 热词 RAG 纠错
        if Config.hot_enabled:
            text = self.corrector.correct(text)
            
        # 2. 自定义规则替换
        if Config.hot_rule:
            text = hot_sub_rule.热词替换(text)
        
        return text
    
    def start_file_watcher(self) -> Observer:
        """
        启动文件监视
        
        Returns:
            文件监视器实例
        """
        self._observer = Observer()
        handler = _HotwordFileHandler(self)
        self._observer.schedule(handler, '.', recursive=False)
        self._observer.start()
        logger.debug("热词文件监视已启动")
        return self._observer
    
    def stop_file_watcher(self) -> None:
        """停止文件监视"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.debug("热词文件监视已停止")


class _HotwordFileHandler(FileSystemEventHandler):
    """热词文件变化处理器"""
    
    _debounce_delay = 3
    
    def __init__(self, manager: HotwordManager):
        super().__init__()
        self.manager = manager
        self._last_event = None
        self._timer = None
        self._lock = threading.Lock()
        
        self._updates: Dict[Path, Callable] = {
            HOTWORD_FILES['hot']: manager._load_hot,
            HOTWORD_FILES['rule']: manager._load_rule,
        }
    
    def on_modified(self, event):
        """文件修改时触发"""
        event_path = Path(event.src_path)
        if event_path not in self._updates:
            return
        
        current_time = time.time()
        
        with self._lock:
            self._last_event = (event_path, current_time)
            
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()
    
    def _debounced_worker(self):
        """防抖工作线程"""
        while True:
            time.sleep(self._debounce_delay)
            
            with self._lock:
                if self._last_event is None:
                    break
                
                event_path, event_time = self._last_event
                current_time = time.time()
                
                if current_time - event_time < self._debounce_delay:
                    continue
                
                self._last_event = None
            
            time.sleep(0.2)
            console.print('[green4]检测到配置文件更新，[/]', end='')
            
            try:
                self._updates[event_path]()
                console.line()
                logger.info(f"热词文件已重新加载: {event_path.name}")
            except Exception as e:
                console.print(f'更新热词失败：{e}', style='bright_red')
                logger.error(f"更新热词失败: {e}", exc_info=True)
            
            break

