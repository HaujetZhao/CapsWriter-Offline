"""
LLM 配置文件监控

功能：
1. 监控 LLM/ 目录的文件变化
2. 自动重载修改的角色配置（防抖 + 延迟执行）
3. 打印角色信息
"""

import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.llm.llm_constants import WatcherConstants
from util.llm.llm_role_formatter import RoleFormatter


class LLMFileWatcher(FileSystemEventHandler):
    """LLM 配置文件监控"""

    def __init__(self, handler):
        self.handler = handler
        self.observer = Observer()
        from config import BASE_DIR
        self.base_dir = Path(BASE_DIR)
        self.llm_dir = self.base_dir / 'LLM'

        # 防抖 + 延迟执行
        self._last_event = None  # (file_path, time)
        self._timer = None
        self._lock = threading.Lock()
        self._debounce_delay = WatcherConstants.DEBOUNCE_DELAY
        
        # 需要监控的配置文件
        self.watched_files = {
            'hot-llm.txt': self._reload_hotwords,
            'hot-llm-rectify.txt': self._reload_rectify,
        }

    def _reload_hotwords(self):
        """重载 LLM 热词"""
        print(f"\n[LLM 监控] 检测到 hot-llm.txt 更新，正在重载...")
        self.handler.rag.load_hotwords()

    def _reload_rectify(self):
        """重载 LLM 纠错历史"""
        print(f"\n[LLM 监控] 检测到 hot-llm-rectify.txt 更新，正在重载...")
        self.handler.rectify_rag.load_history()

    def on_modified(self, event):
        """文件修改时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        file_name = Path(file_path).name

        # 检查是否是监控的配置文件
        if file_name in self.watched_files:
            self.watched_files[file_name]()
            return

        # 检查是否是 LLM 目录下的 .py 文件
        if not file_path.endswith(WatcherConstants.PY_EXTENSION):
            return

        if WatcherConstants.CACHE_DIR in file_path:
            return
            
        # 确保只响应文件在 LLM 目录下的变化 (或者子目录)
        if str(self.llm_dir) not in file_path:
             return

        # 记录最后一次修改事件
        current_time = time.time()

        with self._lock:
            self._last_event = (file_path, current_time)

            # 如果没有运行的定时器，启动一个
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def on_created(self, event):
        """文件创建时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        
        # 暂时只关心 LLM 目录下的 py 文件创建
        if not file_path.endswith(WatcherConstants.PY_EXTENSION):
            return

        if WatcherConstants.CACHE_DIR in file_path:
            return
            
        if str(self.llm_dir) not in file_path:
            return

        # 新文件创建，重新加载所有角色
        current_time = time.time()

        with self._lock:
            self._last_event = (WatcherConstants.RELOAD_ALL_MARKER, current_time)

            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def on_deleted(self, event):
        """文件删除时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        
        if not file_path.endswith(WatcherConstants.PY_EXTENSION):
            return

        if WatcherConstants.CACHE_DIR in file_path:
            return
            
        if str(self.llm_dir) not in file_path:
            return

        # 文件被删除，需要重新加载所有角色并清理
        current_time = time.time()

        with self._lock:
            self._last_event = (WatcherConstants.RELOAD_ALL_MARKER, current_time)

            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def on_moved(self, event):
        """文件移动或重命名时触发"""
        if event.is_directory:
            return

        src_path = str(event.src_path)
        dest_path = str(event.dest_path)

        # 检查是否是 .py 文件
        is_py_file = src_path.endswith('.py') or dest_path.endswith('.py')

        if not is_py_file:
            return

        if '__pycache__' in src_path or '__pycache__' in dest_path:
            return
            
        if str(self.llm_dir) not in src_path and str(self.llm_dir) not in dest_path:
            return

        # 文件重命名，重新加载所有角色
        current_time = time.time()

        with self._lock:
            self._last_event = (WatcherConstants.RELOAD_ALL_MARKER, current_time)

            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    # ... (debounced_worker and do_reload remain same)

    def start(self):
        """启动监控"""
        # 监控 LLM 目录 (递归? recursive=False in original)
        self.observer.schedule(self, str(self.llm_dir), recursive=False)
        # 同时也监控 Base 目录（为了 hot files），non-recursive
        self.observer.schedule(self, str(self.base_dir), recursive=False)
        
        self.observer.start()

        # 打印所有已加载角色信息
        self._print_all_roles()

    def stop(self):
        """停止监控"""
        self.observer.stop()
        self.observer.join()

    def _print_all_roles(self):
        """打印所有已加载的角色信息"""
        print(f"LLM 角色")

        roles = self.handler.roles

        if not roles:
            print("未加载任何角色")
            return

        for role_name, role_config in roles.items():
            self._print_role_info(role_name, role_config)

        print(f"")

    def _print_role_info(self, role_name: str, role_config):
        """打印单个角色信息（使用 Rich 带颜色格式）"""
        RoleFormatter.print_status(role_name, role_config)
