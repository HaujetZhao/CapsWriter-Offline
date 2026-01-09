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


class LLMFileWatcher(FileSystemEventHandler):
    """LLM 配置文件监控"""

    def __init__(self, handler):
        self.handler = handler
        self.observer = Observer()
        self.llm_dir = Path(__file__).parent.parent / 'LLM'

        # 防抖 + 延迟执行
        self._last_event = None  # (file_path, time)
        self._timer = None
        self._lock = threading.Lock()
        self._debounce_delay = 3  # 3秒后执行

    def on_modified(self, event):
        """文件修改时触发"""
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.endswith('.py'):
            return

        if '__pycache__' in file_path:
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

        file_path = event.src_path

        if not file_path.endswith('.py'):
            return

        if '__pycache__' in file_path:
            return

        # 新文件创建，重新加载所有角色
        current_time = time.time()

        with self._lock:
            self._last_event = ('__reload_all__', current_time)

            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def on_deleted(self, event):
        """文件删除时触发"""
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.endswith('.py'):
            return

        if '__pycache__' in file_path:
            return

        # 文件被删除，需要重新加载所有角色并清理
        current_time = time.time()

        with self._lock:
            self._last_event = ('__reload_all__', current_time)

            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounced_worker, daemon=True)
                self._timer.start()

    def on_moved(self, event):
        """文件移动或重命名时触发"""
        if event.is_directory:
            return

        src_path = event.src_path
        dest_path = event.dest_path

        # 检查是否是 .py 文件
        is_py_file = src_path.endswith('.py') or dest_path.endswith('.py')

        if not is_py_file:
            return

        if '__pycache__' in src_path or '__pycache__' in dest_path:
            return

        # 文件重命名，重新加载所有角色
        current_time = time.time()

        with self._lock:
            self._last_event = ('__reload_all__', current_time)

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

                file_path, event_time = self._last_event
                current_time = time.time()

                # 检查是否有新的修改
                if current_time - event_time < self._debounce_delay:
                    # 还有新的修改，继续等待
                    continue

                # 没有新修改超过 3 秒，执行重载
                self._last_event = None

            # 执行重载
            self._do_reload(file_path)

            # 退出线程
            break

    def _do_reload(self, file_path: str):
        """执行重载"""
        # 检查是否需要重新加载所有角色
        if file_path == '__reload_all__':
            self.handler.role_loader.load_all_roles()
            self.handler.reload_roles()

            # 打印更新后的所有角色
            print(f"\nLLM 角色（已更新）")
            self._print_all_roles()
            return

        file_name = Path(file_path).stem

        success, error = self.handler.role_loader.reload_role(file_path)

        if success:
            self.handler.reload_roles()

            # 直接从角色列表中获取更新的角色配置
            # 因为重载后，角色名可能已经改变（通过配置中的 name 字段）
            role_config = None
            role_name = None

            # 遍历所有角色，找到匹配的
            for r_name, r_config in self.handler.roles.items():
                # 检查是否是通过这个文件加载的角色
                if r_config.get('module_name') == f"LLM.{file_name}":
                    role_name = r_name
                    role_config = r_config
                    break

            if role_config:
                from util.llm_role_loader import RoleLoader
                from rich.console import Console
                from rich.text import Text

                loader = RoleLoader()
                console = Console()
                status_line = loader.format_role_status(role_name, role_config)

                # 构建 "角色更新  " 前缀 + 状态行
                prefix = Text("\n角色更新  ")
                prefix.append(status_line)
                console.print(prefix)

        else:
            print(f"\n[LLM 监控] ✗ 重载失败: {file_name}")
            print(f"  错误: {error}")

    def start(self):
        """启动监控"""
        self.observer.schedule(self, str(self.llm_dir), recursive=False)
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

    def _print_role_info(self, role_name: str, role_config: dict):
        """打印单个角色信息（使用 Rich 带颜色格式）"""
        from util.llm_role_loader import RoleLoader
        from rich.console import Console
        from rich.text import Text

        # 使用统一格式化函数（带颜色）
        loader = RoleLoader()
        console = Console()
        status_line = loader.format_role_status(role_name, role_config)

        # 在前面添加两个空格
        prefix = Text("  ")
        prefix.append(status_line)
        console.print(prefix)
