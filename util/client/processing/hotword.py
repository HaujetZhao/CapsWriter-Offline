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
from util.tools import hot_sub_zh, hot_sub_en, hot_sub_rule, hot_kwds
from config import ClientConfig as Config
from util.logger import get_logger

# 日志记录器
logger = get_logger('client')

# 热词文件路径
HOTWORD_FILES = {
    'zh': Path('hot-zh.txt'),
    'en': Path('hot-en.txt'),
    'rule': Path('hot-rule.txt'),
    'kwds': Path('keywords.txt'),
    'llm': Path('hot-llm.txt'),
}


class HotwordManager:
    """
    热词管理器
    
    负责热词的加载、替换和动态更新。
    """
    
    def __init__(self):
        """初始化热词管理器"""
        self._observer: Optional[Observer] = None
    
    def load_all(self) -> None:
        """加载所有热词文件"""
        logger.info("正在加载热词...")
        self._load_zh()
        self._load_en()
        self._load_rule()
        self._load_kwds()
        self._load_llm()
        console.line()
        logger.info("热词加载完成")
    
    def _load_zh(self) -> None:
        """加载中文热词"""
        path = HOTWORD_FILES['zh']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置中文热词，每行一个，开头带井号表示注释，会被省略')
        
        with open(path, 'r', encoding='utf-8') as f:
            num = hot_sub_zh.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num:5}[/] 条中文热词')
        logger.debug(f"载入 {num} 条中文热词")
    
    def _load_en(self) -> None:
        """加载英文热词"""
        path = HOTWORD_FILES['en']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置英文热词 \n# Put English hot words here, one per line.')
        
        with open(path, 'r', encoding='utf-8') as f:
            num = hot_sub_en.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num:5}[/] 条英文热词')
        logger.debug(f"载入 {num} 条英文热词")
    
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
    
    def _load_kwds(self) -> None:
        """加载日记关键词"""
        path = HOTWORD_FILES['kwds']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置日记关键词\n重要\n健康\n学习')
        
        with open(path, 'r', encoding='utf-8') as f:
            num = hot_kwds.do_updata_kwd(f.read())
        console.print(f'已载入 [green4]{num:5}[/] 条日记关键词')
        logger.debug(f"载入 {num} 条日记关键词")
    
    def _load_llm(self) -> None:
        """加载 LLM 热词"""
        path = HOTWORD_FILES['llm']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置 LLM 热词')
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith('#')
            ]
            num = len(lines)
        console.print(f'已载入 [green4]{num:5}[/] 条 LLM 热词')
        logger.debug(f"载入 {num} 条 LLM 热词")
    
    def substitute(self, text: str) -> str:
        """
        执行热词替换
        
        Args:
            text: 原始文本
            
        Returns:
            替换后的文本
        """
        original = text
        
        if Config.hot_zh:
            text = hot_sub_zh.热词替换(text)
        if Config.hot_en:
            text = hot_sub_en.热词替换(text)
        if Config.hot_rule:
            text = hot_sub_rule.热词替换(text)
        
        if text != original:
            logger.debug(f"热词替换: '{original[:30]}...' -> '{text[:30]}...'")
        
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
    
    _debounce_delay = 5
    
    def __init__(self, manager: HotwordManager):
        super().__init__()
        self.manager = manager
        self._last_event = None
        self._timer = None
        self._lock = threading.Lock()
        
        self._updates: Dict[Path, Callable] = {
            HOTWORD_FILES['zh']: manager._load_zh,
            HOTWORD_FILES['en']: manager._load_en,
            HOTWORD_FILES['rule']: manager._load_rule,
            HOTWORD_FILES['kwds']: manager._load_kwds,
            HOTWORD_FILES['llm']: manager._load_llm,
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
