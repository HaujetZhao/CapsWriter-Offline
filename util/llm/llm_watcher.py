"""
LLM 配置文件监控

功能：
1. 监控 LLM/ 目录的文件变化
2. 自动重载修改的角色配置（防抖 + 延迟执行）
3. 打印角色信息

解耦设计：
- 使用回调函数访问 Handler，避免直接依赖 Handler 的内部结构
"""

import time
import threading
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.llm.llm_constants import WatcherConstants
from util.llm.llm_role_formatter import RoleFormatter
from . import logger



class LLMFileWatcher(FileSystemEventHandler):
    """LLM 配置文件监控
    
    使用回调函数与 Handler 交互，实现松耦合设计。
    """

    def __init__(
        self,
        on_roles_reload: Callable[[], None],
        get_roles: Callable[[], Dict[str, Any]],
    ):
        """初始化文件监控器

        Args:
            on_roles_reload: 角色配置重载回调
            get_roles: 获取当前角色列表的回调
        """
        # 回调函数
        self._on_roles_reload = on_roles_reload
        self._get_roles = get_roles
        
        self.observer = Observer()
        from config_client import BASE_DIR
        self.base_dir = Path(BASE_DIR)
        self.llm_dir = self.base_dir / 'LLM'

        # 防抖 + 延迟执行
        self._last_event: Optional[tuple] = None  # (file_path, time)
        self._timer: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._debounce_delay = WatcherConstants.DEBOUNCE_DELAY

        # 需要监控的配置文件及其处理函数
        # 注意：hot-rectify.txt 由热词 watchdog 统一管理，不在 LLM watcher 中处理
        self._watched_files = {}

        logger.debug("LLMFileWatcher 初始化完成")

    def _is_llm_py_file(self, file_path: str) -> bool:
        """检查是否是 LLM 目录下的有效 .py 文件"""
        if not file_path.endswith(WatcherConstants.PY_EXTENSION):
            return False
        if WatcherConstants.CACHE_DIR in file_path:
            return False
        # 使用 Path 进行更严谨的路径比较
        try:
            path = Path(file_path).resolve()
            return path.parent == self.llm_dir.resolve()
        except Exception:
            return False

    def on_modified(self, event):
        """文件修改时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        file_name = Path(file_path).name

        # 检查是否是监控的配置文件
        if file_name in self._watched_files:
            self._watched_files[file_name]()
            return

        # 检查是否是 LLM 目录下的 .py 文件
        if not self._is_llm_py_file(file_path):
            return

        self._schedule_reload(file_path)

    def on_created(self, event):
        """文件创建时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        
        if not self._is_llm_py_file(file_path):
            return

        # 新文件创建，重新加载所有角色
        self._schedule_reload(WatcherConstants.RELOAD_ALL_MARKER)

    def on_deleted(self, event):
        """文件删除时触发"""
        if event.is_directory:
            return

        file_path = str(event.src_path)
        
        if not self._is_llm_py_file(file_path):
            return

        # 文件被删除，需要重新加载所有角色
        self._schedule_reload(WatcherConstants.RELOAD_ALL_MARKER)

    def on_moved(self, event):
        """文件移动或重命名时触发"""
        if event.is_directory:
            return

        src_path = str(event.src_path)
        dest_path = str(event.dest_path)

        # 检查是否涉及 .py 文件
        if not (self._is_llm_py_file(src_path) or self._is_llm_py_file(dest_path)):
            return

        # 文件重命名，重新加载所有角色
        self._schedule_reload(WatcherConstants.RELOAD_ALL_MARKER)

    def _schedule_reload(self, file_path: str):
        """调度重载操作（带防抖）"""
        current_time = time.time()

        with self._lock:
            self._last_event = (file_path, current_time)

            # 如果没有运行的定时器，启动一个
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def _debounced_worker(self):
        """防抖工作线程"""
        while True:
            with self._lock:
                if self._last_event is None:
                    break
                
                _, last_time = self._last_event
                current_time = time.time()
                
                # 如果时间还没到，继续等待
                if current_time - last_time < self._debounce_delay:
                    pass
                else:
                    # 时间到了，执行重载
                    event_info = self._last_event
                    self._last_event = None
                    # 释放锁执行耗时操作
                    self._lock.release()
                    try:
                        self._do_reload(event_info[0])
                    finally:
                        self._lock.acquire()
                    break
            
            time.sleep(0.1)

    def _do_reload(self, file_path: str):
        """执行重载操作"""
        if file_path == WatcherConstants.RELOAD_ALL_MARKER:
            logger.info("检测到文件变化，正在重新加载所有角色...")
            print(f"\n[LLM 监控] 检测到文件变化，正在重新加载所有角色...")
            self._on_roles_reload()
            self._print_all_roles()
        else:
            file_name_stem = Path(file_path).stem
            module_name = f"LLM.{file_name_stem}"
            
            logger.debug(f"检测到文件变化: {Path(file_path).name}")
            self._on_roles_reload()
            
            # 只查找并打印与该文件相关的角色
            roles = self._get_roles()
            found = False
            for role_name, role_config in roles.items():
                # 检查 module_name 是否匹配
                if role_config.module_name == module_name:
                    self._print_role_info(role_name, role_config)
                    found = True
            
            if not found:
                # 可能是文件名和内部 role.name 不对应
                logger.debug(f"未找到直接对应文件 '{file_name_stem}' 的角色，显示所有角色")
                print(f"（未找到直接对应文件 '{file_name_stem}' 的角色，显示所有角色）")
                self._print_all_roles()

    def start(self):
        """启动监控"""
        # 监控 LLM 目录
        self.observer.schedule(self, str(self.llm_dir), recursive=False)
        # 同时也监控 Base 目录（为了 hot files），non-recursive
        self.observer.schedule(self, str(self.base_dir), recursive=False)
        
        self.observer.start()
        logger.info("LLM 文件监控已启动")

        # 打印所有已加载角色信息
        self._print_all_roles()

    def stop(self):
        """停止监控"""
        self.observer.stop()
        self.observer.join()
        logger.info("LLM 文件监控已停止")

    def _print_all_roles(self):
        """打印所有已加载的角色信息"""
        print(f"\nLLM 角色")

        roles = self._get_roles()

        if not roles:
            print("未加载任何角色")
            return

        for role_name, role_config in roles.items():
            self._print_role_info(role_name, role_config)

        print(f"")

    def _print_role_info(self, role_name: str, role_config):
        """打印单个角色信息（使用 Rich 带颜色格式）"""
        RoleFormatter.print_status(role_name, role_config)
