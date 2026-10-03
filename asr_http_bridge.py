# coding: utf-8
"""
CapsWriter Offline HTTP 桥接服务（持久连接版）
============================================
启动后保持与 CapsWriter WebSocket 的长连接，HTTP 请求即时转发，
避免每次转写都重新握手，大幅降低延迟。

用法：
    python asr_http_bridge.py
    监听 http://127.0.0.1:6017

接口：
    POST /transcribe
    Body: {"audio": "<base64 PCM>", "language": "auto"}
    返回: {"text": "..."}
"""

import json
import sys
import os
import time
import uuid
import asyncio
import base64
import threading
import queue

try:
    import websockets
except ImportError as e:
    print(f'[错误] 缺少 websockets，请运行: pip install websockets')
    input('按回车键退出...')
    sys.exit(1)

from http.server import HTTPServer, BaseHTTPRequestHandler

WS_URL = 'ws://127.0.0.1:6016'
HTTP_PORT = 6017

# PCM 参数（与 CapsWriter 一致）
SAMPLE_RATE = 16000
BYTES_PER_SEC = SAMPLE_RATE * 4  # float32 mono = 64000 bytes/s
CHUNK_SECS = 60                   # 每次发送60秒音频
CHUNK_BYTES = BYTES_PER_SEC * CHUNK_SECS
SEG_DURATION = 60                 # 分段长度（与客户端一致）
SEG_OVERLAP = 4                   # 分段重叠（与客户端一致）

# 全局状态
_loop = None
_send_q = None           # (task_id, audio_b64, language, future) 队列
_pending = {}            # task_id → asyncio.Future 映射
_ws_ready = threading.Event()


async def _ws_sender(ws):
    """协程：从队列取音频，分块发送到 CapsWriter（模拟客户端流式发送）"""
    while True:
        try:
            task_id, audio_b64, language = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _send_q.get()
            )
            if task_id is None:
                break

            # 解码 base64 → 原始 PCM bytes
            pcm_bytes = base64.b64decode(audio_b64)
            total_secs = len(pcm_bytes) / BYTES_PER_SEC
            print(f'[Bridge] 开始分块发送: {total_secs:.1f}s 音频, 任务={task_id}')

            offset = 0
            chunk_idx = 0
            while offset < len(pcm_bytes):
                chunk = pcm_bytes[offset:offset + CHUNK_BYTES]
                offset += len(chunk)
                is_last = (offset >= len(pcm_bytes))
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')

                msg = {
                    'task_id': task_id,
                    'source': 'file',
                    'data': chunk_b64,
                    'is_final': False,
                    'time_start': time.time(),
                    'seg_duration': SEG_DURATION,
                    'seg_overlap': SEG_OVERLAP,
                    'context': '',
                    'language': language
                }
                await ws.send(json.dumps(msg, ensure_ascii=False))
                chunk_idx += 1
                progress = min(offset / BYTES_PER_SEC, total_secs)
                print(f'  块{chunk_idx}: {progress:.1f}s/{total_secs:.1f}s {"[最后]" if is_last else ""}')

                if not is_last:
                    await asyncio.sleep(0.1)  # 微延迟，避免服务端积压

            # 发送结束标志
            final_msg = {
                'task_id': task_id,
                'source': 'file',
                'data': '',
                'is_final': True,
                'time_start': time.time(),
                'seg_duration': SEG_DURATION,
                'seg_overlap': SEG_OVERLAP,
                'context': '',
                'language': language
            }
            await ws.send(json.dumps(final_msg, ensure_ascii=False))
            print(f'[Bridge] 音频发送完毕，等待识别结果...')

        except Exception as e:
            print(f'[Bridge] 发送失败: {e}')
            for tid, fut in list(_pending.items()):
                if not fut.done():
                    fut.set_result('')
            _pending.clear()
            break


async def _ws_receiver(ws):
    """协程：接收 CapsWriter 结果，匹配到对应请求"""
    try:
        async for raw in ws:
            try:
                resp = json.loads(raw)
                tid = resp.get('task_id', '')
                if resp.get('is_final') and resp.get('text') and tid in _pending:
                    _pending.pop(tid).set_result(resp['text'])
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f'[Bridge] 接收断开: {e}')
        for tid, fut in list(_pending.items()):
            if not fut.done():
                fut.set_result('')
        _pending.clear()


async def _ws_maintain():
    """协程：维持与 CapsWriter 的持久 WebSocket 连接，断线自动重连"""
    global _ws_ready
    retry_delay = 1  # 初始重连间隔
    while True:
        try:
            print(f'[Bridge] 正在连接 CapsWriter ({WS_URL})...')
            async with websockets.connect(
                WS_URL, ping_interval=20, ping_timeout=10,
                close_timeout=5, subprotocols=['binary'], max_size=None
            ) as ws:
                print('[Bridge] ✅ CapsWriter 已连接（持久）')
                _ws_ready.set()
                retry_delay = 1  # 连接成功，重置重连间隔
                sender_task = asyncio.create_task(_ws_sender(ws))
                receiver_task = asyncio.create_task(_ws_receiver(ws))
                done, pending = await asyncio.wait(
                    [sender_task, receiver_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                _ws_ready.clear()
                print(f'[Bridge] WebSocket 断开，{retry_delay}秒后重连...')
        except Exception as e:
            _ws_ready.clear()
            print(f'[Bridge] 连接失败: {e}，{retry_delay}秒后重连...')
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)  # 指数退避，最多30秒


async def _transcribe_async(audio_b64: str, language: str) -> str:
    """异步转写：加入队列，等待 WebSocket 返回结果"""
    task_id = f'bridge_{uuid.uuid4().hex[:8]}'
    fut = asyncio.get_event_loop().create_future()
    _pending[task_id] = fut
    _send_q.put((task_id, audio_b64, language))
    try:
        return await asyncio.wait_for(fut, timeout=120)
    except asyncio.TimeoutError:
        _pending.pop(task_id, None)
        return ''


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器（在独立线程中运行）"""

    def _reply(self, text: str):
        resp = json.dumps({'text': text}, ensure_ascii=False)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(resp.encode('utf-8'))

    def do_GET(self):
        if self.path == '/health':
            status = 'ok' if _ws_ready.is_set() else 'waiting'
            self._reply(status)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != '/transcribe':
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            req = json.loads(body)
            audio_b64 = req.get('audio', '')
            language = req.get('language', 'auto')
            if not audio_b64:
                self.send_error(400, 'Missing audio field')
                return

            # 跨线程调用异步转写
            future = asyncio.run_coroutine_threadsafe(
                _transcribe_async(audio_b64, language), _loop
            )
            text = future.result(timeout=130)
            self._reply(text)
            print(f'[Bridge] 转写完成: {text[:80]}...' if len(text) > 80 else f'[Bridge] 转写完成: {text}')
        except Exception as e:
            print(f'[Bridge] 处理请求出错: {e}')
            self.send_error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass


def _run_http_server():
    """在后台线程运行 HTTP 服务器"""
    server = HTTPServer(('127.0.0.1', HTTP_PORT), BridgeHandler)
    server.serve_forever()


def main():
    global _loop, _send_q

    print('=' * 48)
    print('  CapsWriter HTTP 桥接服务（持久连接）')
    print(f'  监听: http://127.0.0.1:{HTTP_PORT}')
    print(f'  后端: {WS_URL}')
    print('=' * 48)
    print('  按 Ctrl+C 停止')
    print()

    _send_q = queue.Queue()
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    # 启动 HTTP 服务器线程
    http_thread = threading.Thread(target=_run_http_server, daemon=True)
    http_thread.start()
    print(f'[Bridge] HTTP 服务已启动')

    # 主线程运行 asyncio 事件循环（WebSocket 持久连接）
    try:
        _loop.run_until_complete(_ws_maintain())
    except KeyboardInterrupt:
        print('\n[Bridge] 服务已停止')
    finally:
        _send_q.put((None, '', ''))  # 通知发送协程退出
        _loop.stop()
        _loop.close()


if __name__ == '__main__':
    main()
