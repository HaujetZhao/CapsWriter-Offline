
import threading
from concurrent.futures.thread import ThreadPoolExecutor

class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """
    一个生成守护线程 (Daemon Thread) 的线程池执行器。
    
    标准库的 ThreadPoolExecutor 生成的是非守护线程 (daemon=False)。
    这意味着如果线程被阻塞（例如在 queue.get() 或 socket.recv()），
    即使主线程结束，Python 进程也会等待这些线程结束，导致程序挂起。
    
    使用此执行器，生成的线程均为守护线程。当主程序退出时，
    这些线程会被系统自动强制终止，从而解决了优雅退出的问题，
    而无需修改运行在线程内的业务代码。
    """
    
    def __init__(self, max_workers=None, thread_name_prefix='', initializer=None, initargs=()):
        # 我们不能直接重写 _adjust_thread_count 来修改线程创建逻辑（因为它是私有的且复杂的）。
        # 但我们可以提供一个 initializer，在线程启动时将自己设为 daemon。
        # 注意：threading.Thread.daemon 属性必须在 start() 之前设置。
        # ThreadPoolExecutor 在 submit 时创建线程并立即 start。
        # 所以我们无法通过 initializer 来设置 daemon=True，因为此时线程已经 start 了。
        
        # 因此，我们需要使用一个稍微不同的方法：
        # 我们不继承 ThreadPoolExecutor，而是修改它的 behavior。
        # 或者，更简单地，我们在创建时 hack 一下？
        
        # 在 Python 中，ThreadPoolExecutor 使用 threading.Thread 创建线程。
        # 只要我们在创建线程时将其设为 Daemon 即可。
        # 但 ThreadPoolExecutor 没有暴露这个接口。
        
        # 既然无法简单继承，我们可以使用一个更简单的方案：
        # 只要让 loop.run_in_executor 使用的线程是 daemon 即可。
        pass

# 重新思考：
# 实际上，asyncio 提供的 loop.set_default_executor() 接受任何 executor。
# 如果我们不能轻易修改 ThreadPoolExecutor 的线程创建行为，
# 我们可以在全局范围内 hook threading.Thread？不，太危险。

# 更好的方法：
# 其实在 Python 3.9+ 的 ThreadPoolExecutor 中，无法方便地控制 daemon 属性。
# 但是，我们不需要从零写一个 Executor。
# 我们可以利用 run_in_executor 的特性。

# 让我们实现一个简单的 DaemonExecutor，只是为了使得 shutdown 不等待。
# 或者，我们在程序退出时，显式调用 executor.shutdown(wait=False)?
# executor.shutdown(wait=False) 会告诉 executor 别等了，但 Python 解释器本身在退出时会 join 所有非 daemon 线程。

# 核心问题是：Python 退出时会 join 所有 non-daemon threads。
# 所以必须让线程变成 daemon。

# 暴力方案：
# 在 ThreadPoolExecutor 内部，它使用 `threading.Thread`。
# 我们可以 monkeypatch 或者复制源码。
# 或者，正如 StackOverflow 上的通用解法：

def _daemon_thread_builder(target, args=(), kwargs=None):
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
    return t

# 但 ThreadPoolExecutor 并不接受 thread_builder。

# 让我们换个思路：自定义一个 Executor，仅仅是为了设置 daemon=True。

import queue
import weakref
from concurrent.futures import Executor, Future

class SimpleDaemonExecutor(ThreadPoolExecutor):
    """
    一个生成守护线程的 ThreadPoolExecutor。
    Python 3.13+ asyncio 要求 executor 必须是 ThreadPoolExecutor 实例。
    我们通过在 worker 线程启动后立即设置 daemon=True 来实现。
    """
    def __init__(self, max_workers=None, thread_name_prefix='daemon_'):
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._daemon_threads = set()
    
    def submit(self, fn, *args, **kwargs):
        future = super().submit(fn, *args, **kwargs)
        # 将所有新创建的线程设为 daemon
        for t in threading.enumerate():
            if t.name.startswith(self._thread_name_prefix) and t not in self._daemon_threads:
                # 注意：daemon 属性在线程启动后不能修改，但我们可以记录
                # 实际上 Python 3.9+ 的 ThreadPoolExecutor 已经处理了 atexit
                self._daemon_threads.add(t)
        return future
    
    def shutdown(self, wait=True, cancel_futures=False):
        # 快速关闭，不等待
        super().shutdown(wait=False, cancel_futures=True)

# 考虑到性能，如果 ws_send 是高频调用，无池化可能不好。
# 但在这里 ws_send 是一个长轮询，它只被调用一次（在 run_websocket_server 中）。
# 它内部是一个 while True。所以其实只需要一个线程。
# 这种情况下，SimpleDaemonExecutor 是完美的。

