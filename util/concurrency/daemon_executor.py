
import threading
import queue
import weakref
from concurrent.futures import Future, ThreadPoolExecutor

class SimpleDaemonExecutor(ThreadPoolExecutor):
    """
    一个极其简单的 Executor，为每个任务创建一个守护线程。
    注意：这没有池化（Pooling），每个任务一个线程。
    对于 IO 密集型且任务数量不多的场景（如 ws_send, ws_recv），这是完全可以接受的。
    而且这保证了真正的 Daemon 行为。
    """
    def submit(self, fn, *args, **kwargs):
        f = Future()
        
        def wrapper():
            try:
                result = fn(*args, **kwargs)
                f.set_result(result)
            except Exception as e:
                f.set_exception(e)

        t = threading.Thread(target=wrapper, daemon=True)
        t.start()
        return f
    
    def shutdown(self, wait=True):
        pass

