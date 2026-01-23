# coding: utf-8
"""
热词管理模块

提供 HotwordManager 类用于管理热词的加载、替换和文件监视。
"""

from __future__ import annotations

import threading
import time
import unicodedata
from pathlib import Path
from typing import Dict, Optional, Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from rich.console import Console

from .hot_phoneme import PhonemeCorrector

from . import logger
console = Console(highlight=False)

# 全局单例
_manager: Optional[HotwordManager] = None

class HotwordManager:
    """热词管理器：负责热词加载、替换和文件监控"""

    def __init__(self,
                 hotword_file: Optional[Path] = None,
                 threshold: float = 0.7,
                 similar_threshold: Optional[float] = None):
        """
        初始化
        Args:
            hotword_file: 热词文件路径
            threshold: 纠错阈值
            similar_threshold: 相似度阈值
        """
        self.file = hotword_file or Path('hot.txt')
        self.threshold = threshold
        self.similar_threshold = similar_threshold

        # 初始化热词纠错器
        self.phoneme_corrector = PhonemeCorrector(threshold=threshold, similar_threshold=similar_threshold)
        self._observer: Optional[Observer] = None

    def _get_display_width(self, text: str) -> int:
        """计算字符串的显示宽度（考虑中文字符占2个单位）"""
        width = 0
        for char in text:
            if unicodedata.east_asian_width(char) in ('W', 'F', 'A'):
                width += 2
            else:
                width += 1
        return width

    def _format_msg(self, label: str, filename: str, count: int) -> str:
        """格式化对齐消息"""
        w = self._get_display_width(label)
        padding1 = " " * max(0, 6 - w)
        w2 = self._get_display_width(filename)
        padding2 = " " * max(0, 8 - w2)
        return f"[bold cyan]      {label}{padding1}：[/][cyan]{filename}{padding2}[/] 已更新[green]{count:3d}[/]条"

    def load(self) -> None:
        """加载热词文件"""
        logger.info("正在加载热词资源...")
        self._load_hot()
        logger.info("热词资源加载完成")

    def _read_file(self) -> str:
        """读取热词文件"""
        try:
            if not self.file.exists():
                # 缺失则创建空文件
                self.file.parent.mkdir(parents=True, exist_ok=True)
                self.file.write_text("# 热词文件单行一个\n", encoding='utf-8')
                return ""
            return self.file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"读取文件失败 {self.file}: {e}")
            return ""

    def _load_hot(self) -> None:
        content = self._read_file()
        num = self.phoneme_corrector.update_hotwords(content)
        console.print(self._format_msg("热词库", self.file.name, num))

    def get_corrector(self) -> PhonemeCorrector:
        """获取热词纠错器"""
        return self.phoneme_corrector

    def start_file_watcher(self) -> Any:
        """启动文件监视"""
        if self._observer: return

        self._observer = Observer()
        handler = _HotwordFileHandler(self)

        # 监视热词文件所在目录
        watch_dir = self.file.parent.absolute()
        self._observer.schedule(handler, path=str(watch_dir), recursive=False)

        self._observer.start()
        logger.debug(f"已启动热词文件监视: {watch_dir}")
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

    def on_modified(self, event):
        """文件修改时触发"""
        if event.is_directory: return

        event_path = Path(event.src_path)
        filename = event_path.name

        # 检查是否是我们关心的热词文件
        if filename != self.manager.file.name:
            return

        logger.debug(f"[watchdog] 热词文件变化: {filename}")
        current_time = time.time()

        with self._lock:
            self._last_event = (filename, current_time)
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

                filename, event_time = self._last_event
                if time.time() - event_time < self._debounce_delay:
                    continue

                self._last_event = None

            # 执行加载
            try:
                self.manager._load_hot()
                logger.info(f"热词文件已自动重新加载: {filename}")
            except Exception as e:
                console.print(f'热词自动更新失败：{e}', style='bright_red')
                logger.error(f"更新热词失败: {e}", exc_info=True)
            break


# ======================================================================
# --- 全局单例访问函数 ---

def get_hotword_manager(hotword_file: Optional[Path] = None,
                        threshold: float = 0.7,
                        similar_threshold: Optional[float] = None) -> HotwordManager:
    """
    获取热词管理器单例实例。
    第一次调用时可以传入配置参数，后续调用将返回已存在的实例。
    """
    global _manager
    if _manager is None:
        _manager = HotwordManager(
            hotword_file=hotword_file,
            threshold=threshold,
            similar_threshold=similar_threshold
        )
    return _manager
