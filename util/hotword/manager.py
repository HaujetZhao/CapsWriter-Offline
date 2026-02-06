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
from typing import Dict, Callable, Optional, TYPE_CHECKING, Any, Tuple

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from rich.console import Console

from .hot_rule import RuleCorrector
from .hot_phoneme import PhonemeCorrector
from .hot_rectification import RectificationRAG

# 尝试导入主项目的统一组件，失败则使用本地默认值（独立运行模式）
try:
    from config_client import ClientConfig
    HOT_THRESH = ClientConfig.hot_thresh
    HOT_SIMILAR = ClientConfig.hot_similar
    RECTIFY_THRESH = ClientConfig.hot_rectify
except ImportError:
    HOT_THRESH = 0.8
    HOT_SIMILAR = 0.6
    RECTIFY_THRESH = 0.5

from . import logger

try:
    from util.client.state import console
except ImportError:
    try:
        from rich.console import Console
        console = Console(highlight=False)
    except ImportError:
        class MockConsole:
            def print(self, *args, **kwargs): 
                # rich 格式清洗略去，直接打印内容
                msg = str(args[0]) if args else ""
                print(msg.replace('[cyan]', '').replace('[/]', '').replace('[green4]', ''))
            def line(self): print()
        console = MockConsole()

# 全局单例
_manager: Optional[HotwordManager] = None

class HotwordManager:
    """热词管理器：负责资源协调、热词文件加载与动态监控"""

    def __init__(self, 
                 hotword_files: Optional[Dict[str, Path]] = None,
                 threshold: float = 0.7,
                 similar_threshold: Optional[float] = None,
                 rectify_threshold: float = 0.5):
        """
        初始化
        Args:
            hotword_files: 文件映射 {'hot': Path, 'rule': Path, 'rectify': Path}
            threshold: 纠错阈值
            similar_threshold: 相似度阈值
        """
        self.files = hotword_files or {
            'hot': Path('hot.txt'),
            'rule': Path('hot-rule.txt'),
            'rectify': Path('hot-rectify.txt'),
        }
        
        self.threshold = threshold
        self.similar_threshold = similar_threshold
        self.rectify_threshold = rectify_threshold
        
        # 初始化各个组件
        self.phoneme_corrector = PhonemeCorrector(threshold=threshold, similar_threshold=similar_threshold)
        self.rule_corrector = RuleCorrector()
        self.rectify_rag = RectificationRAG(
            str(self.files.get('rectify', 'hot-rectify.txt')),
            threshold=rectify_threshold
        )
        
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
        padding1 = " " * max(0, 8 - w)
        w2 = self._get_display_width(filename)
        padding2 = " " * max(0, 16 - w2)
        return f"[bold cyan]{label}{padding1}：[/][cyan]{filename}{padding2}[/] 已更新[green]{count:3d}[/]条"

    def load_all(self) -> None:
        """初次加载所有资源"""
        logger.info("正在加载热词资源...")
        self._load_hot()
        self._load_rule()
        self._load_rectify()
        logger.info("热词资源加载完成")

    def _read_file(self, key: str) -> str:
        """读取文件的统一辅助函数"""
        path = self.files.get(key)
        if not path: return ""
        try:
            if not path.exists():
                # 缺失则创建空文件
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# 热词文件单行一个\n", encoding='utf-8')
                return ""
            return path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"读取文件失败 {path}: {e}")
            return ""

    def _load_hot(self) -> None:
        content = self._read_file('hot')
        num = self.phoneme_corrector.update_hotwords(content)
        console.print(self._format_msg("热词库", "hot.txt", num))

    def _load_rule(self) -> None:
        content = self._read_file('rule')
        num = self.rule_corrector.update_rules(content)
        console.print(self._format_msg("规则库", "hot-rule.txt", num))

    def _load_rectify(self) -> None:
        # RectificationRAG 目前是自己加载的，保持其接口一致性
        self.rectify_rag.load_history()
        count = len(self.rectify_rag.records) if hasattr(self.rectify_rag, 'records') else 0
        console.print(self._format_msg("纠错历史", "hot-rectify.txt", count))

    def get_phoneme_corrector(self) -> PhonemeCorrector:
        return self.phoneme_corrector

    def get_rule_corrector(self) -> RuleCorrector:
        return self.rule_corrector

    def get_rectify_rag(self) -> RectificationRAG:
        return self.rectify_rag

    def start_file_watcher(self) -> Any:
        """启动文件监视"""
        if self._observer: return
        
        self._observer = Observer()
        handler = _HotwordFileHandler(self)
        
        # 监视每一个文件所在的目录 (去重后监听)
        watched_dirs = {p.parent.absolute() for p in self.files.values()}
        for d in watched_dirs:
            self._observer.schedule(handler, path=str(d), recursive=False)
            
        self._observer.start()
        logger.debug(f"已启动热词文件监视: {watched_dirs}")
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

        # 映射文件路径名到加载函数
        # 注意：这里直接与 manager.files 动态保持一致
        self._update_mapping()

    def _update_mapping(self):
        m = self.manager
        self._file_mapping = {
            m.files['hot'].name: m._load_hot,
            m.files['rule'].name: m._load_rule,
            m.files['rectify'].name: m._load_rectify,
        }

    def on_modified(self, event):
        """文件修改时触发"""
        if event.is_directory: return
        
        event_path = Path(event.src_path)
        filename = event_path.name
        
        # 检查是否是我们关心的文件
        if filename not in self._file_mapping:
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
            handler = self._file_mapping.get(filename)
            if handler:
                try:
                    handler()
                    logger.info(f"热词文件已自动重新加载: {filename}")
                except Exception as e:
                    console.print(f'热词自动更新失败：{e}', style='bright_red')
                    logger.error(f"更新热词失败: {e}", exc_info=True)
            break


# ======================================================================
# --- 全局单例访问函数 ---

def get_hotword_manager(hotword_files: Optional[Dict[str, Path]] = None, 
                        threshold: float = 0.7, 
                        similar_threshold: Optional[float] = None,
                        rectify_threshold: float = 0.5) -> HotwordManager:
    """
    获取热词管理器单例实例。
    第一次调用时可以传入配置参数，后续调用将返回已存在的实例。
    """
    global _manager
    if _manager is None:
        # 如果是主项目运行，这里可以从 config 拿默认值逻辑可以放在调用端
        _manager = HotwordManager(
            hotword_files=hotword_files,
            threshold=threshold,
            similar_threshold=similar_threshold,
            rectify_threshold=rectify_threshold
        )
    return _manager
