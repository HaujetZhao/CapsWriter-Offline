# coding: utf-8
"""
热词管理模块

提供 HotwordManager 类用于管理热词的加载、替换和文件监视。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Dict, Callable, Optional, TYPE_CHECKING, Any, Tuple

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from util.client.state import console
from util.hotword.hot_rule import RuleCorrector
from util.hotword.hot_phoneme import PhonemeCorrector
from util.hotword.hot_rectification import RectificationRAG
from config import ClientConfig as Config
from util.logger import get_logger

# 日志记录器
logger = get_logger('client')

# 全局单例
_manager: Optional[HotwordManager] = None

# 热词文件路径
HOTWORD_FILES = {
    'hot': Path('hot.txt'),
    'rule': Path('hot-rule.txt'),
    'rectify': Path('hot-rectify.txt'),
}


class HotwordManager:
    """
    热词管理器

    负责热词的加载、管理和动态更新。
    """

    def __init__(self):
        """初始化热词管理器"""
        self._observer: Optional[Observer] = None
        # 使用配置中的双阈值初始化音素纠错器
        self.phoneme_corrector = PhonemeCorrector(
            threshold=Config.hot_thresh,      # 替换阈值（高）
            similar_threshold=Config.hot_similar  # 相似列表阈值（低）
        )
        # 初始化规则纠错器
        self.rule_corrector = RuleCorrector()
        # 初始化纠错历史 RAG
        self.rectify_rag = RectificationRAG('hot-rectify.txt')

    def load_all(self) -> None:
        """加载所有热词文件"""
        logger.info("正在加载热词...")
        self._load_hot()
        self._load_rule()
        self._load_rectify()
        console.line()
        logger.info("热词加载完成")

    def _load_hot(self) -> None:
        """加载热词（统一文件）"""
        path = HOTWORD_FILES['hot']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此放置热词，每行一个，井号开头为注释\n')

        with open(path, 'r', encoding='utf-8') as f:
            num = self.phoneme_corrector.update_hotwords(f.read())

        console.print(f'热词 [cyan]hot.txt[/] 已更新，载入 [green4]{num:5}[/] 条热词')
        logger.debug(f"载入 {num} 条热词")

    def _load_rule(self) -> None:
        """加载自定义规则"""
        path = HOTWORD_FILES['rule']
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置自定义规则\n毫安时 = mAh\n赫兹 = Hz')

        with open(path, 'r', encoding='utf-8') as f:
            num = self.rule_corrector.update_rules(f.read())
        console.print(f'热词 [cyan]hot-rule.txt[/] 已更新，载入 [green4]{num:5}[/] 条自定义替换规则')
        logger.debug(f"载入 {num} 条自定义替换规则")

    def _load_rectify(self) -> None:
        """加载纠错历史"""
        self.rectify_rag.load_history()
        if self.rectify_rag.records:
            console.print(f'热词 [cyan]hot-rectify.txt[/] 已更新，载入 [green4]{len(self.rectify_rag.records)}[/] 条纠错规则')
            logger.debug(f"载入 {len(self.rectify_rag.records)} 条 LLM 纠错历史")

    def get_phoneme_corrector(self) -> PhonemeCorrector:
        """获取音素纠错器"""
        return self.phoneme_corrector

    def get_rule_corrector(self) -> RuleCorrector:
        """获取规则纠错器"""
        return self.rule_corrector

    def get_rectify_rag(self) -> RectificationRAG:
        """获取纠错历史检索器"""
        return self.rectify_rag

    def start_file_watcher(self) -> Any:
        """
        启动文件监视（监视根目录，过滤热词文件）

        Returns:
            文件监视器实例
        """
        self._observer = Observer()
        handler = _HotwordFileHandler(self)

        # 监听根目录（watchdog 需要监听目录，不能直接监听文件）
        self._observer.schedule(handler, path='.', recursive=False)

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

        # 文件映射：文件路径 -> (加载函数, 文件标签)
        self._file_handlers: Dict[Path, Tuple[Callable, str]] = {
            HOTWORD_FILES['hot']: (manager._load_hot, '热词'),
            HOTWORD_FILES['rule']: (manager._load_rule, '自定义规则'),
            HOTWORD_FILES['rectify']: (manager._load_rectify, '纠错历史'),
        }

    def on_modified(self, event):
        """文件修改时触发"""
        event_path = Path(event.src_path)
        logger.debug(f"[watchdog] 检测到文件变化: {event_path}")

        # 忽略目录事件
        if event.is_directory:
            logger.debug(f"[watchdog] 忽略目录事件: {event_path}")
            return

        # 只处理热词文件（通过文件名匹配，兼容相对路径）
        if event_path.name not in [p.name for p in HOTWORD_FILES.values()]:
            logger.debug(f"[watchdog] 非热词文件，忽略: {event_path.name}")
            return

        logger.debug(f"[watchdog] 热词文件变化，准备处理: {event_path.name}")

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

            # 通过文件名查找对应的处理器
            handler_info = None
            for file_path, info in self._file_handlers.items():
                if file_path.name == event_path.name:
                    handler_info = info
                    break

            if handler_info:
                handler, file_label = handler_info

            if handler:
                try:
                    handler()  # 只调用发生变化的文件的加载函数
                    console.line()
                    logger.info(f"热词文件已重新加载: {event_path.name}")
                except Exception as e:
                    console.print(f'更新失败：{e}', style='bright_red')
                    logger.error(f"更新热词失败: {e}", exc_info=True)

            break


# ======================================================================
# --- 全局单例访问函数 ---

def get_hotword_manager() -> HotwordManager:
    """获取热词管理器单例实例"""
    global _manager
    if _manager is None:
        _manager = HotwordManager()
    return _manager
