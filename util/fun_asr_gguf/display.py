"""
显示管理模块

通过线程和队列处理控制台输出，解耦转录逻辑与显示逻辑。
"""

import sys
import queue
import threading
from typing import Optional

class DisplayReporter:
    """负责汇总消息并在后台线程统一打印"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.message_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.current_segment = (0, 0) # (idx, total)
        self.skip_technical = False    # 新增：是否跳过中间技术日志
        self.thread.start()

    def print(self, message: str, force: bool = False):
        """发送普通打印消息"""
        if not self.verbose:
            return
            
        # 在调用 print 的瞬间就生成前缀，避免异步线程导致前缀信息滞后或提前
        prefix = ""
        if self.current_segment[1] > 1 and self.current_segment[0] > 0:
            prefix = f"[{self.current_segment[0]}/{self.current_segment[1]}] "
            
        if force or not self.skip_technical:
            self.message_queue.put(('print', (prefix, message)))

    def stream(self, chunk: str):
        """发送流式吐字消息"""
        if self.verbose:
            self.message_queue.put(('stream', chunk))

    def set_segment(self, current: int, total: int):
        """设置当前处理的分段信息"""
        self.current_segment = (current, total)

    def _run(self):
        """显示线程主循环"""
        last_was_stream = False
        while not (self.stop_event.is_set() and self.message_queue.empty()):
            try:
                msg_type, content = self.message_queue.get(timeout=0.1)
                
                if msg_type == 'print':
                    if last_was_stream:
                        sys.stdout.write("\n")
                        last_was_stream = False
                    
                    prefix, message = content
                    sys.stdout.write(f"{prefix}{message}\n")
                    sys.stdout.flush()
                
                elif msg_type == 'stream':
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    last_was_stream = True
                
                self.message_queue.task_done()
            except queue.Empty:
                continue

    def stop(self):
        """停止显示线程"""
        if self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=1.0)
            # 确保最后刷一次屏幕
            sys.stdout.write("\n")
            sys.stdout.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
