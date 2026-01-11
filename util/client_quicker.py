import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed
from util.client_cosmic import console

__all__ = ['设置Quicker配置', '触发Quicker操作']

# 全局变量，用于保持长连接
_WS_CONNECTION = None

# Quicker 配置
QUICKER_CONFIG = {
    "host": "127.0.0.1",
    "port": 668,
    "password": "" 
}

# 消息序列号
_MSG_SERIAL = 1

async def 获取连接():
    """
    内部辅助函数：获取可用的 WebSocket 连接，如果不存在或已断开则重连
    """
    global _WS_CONNECTION
    
    # 1. 检查现有连接是否可用
    if _WS_CONNECTION:
        # 【关键修复】websockets 库没有 .closed 属性
        # 使用 close_code 判断：None 表示连接正常，否则表示已关闭
        if _WS_CONNECTION.close_code is None:
            return _WS_CONNECTION
        else:
            console.print("连接已断开，准备重连...")
            _WS_CONNECTION = None

    # 2. 建立新连接
    host = QUICKER_CONFIG['host']
    port = QUICKER_CONFIG['port']
    pwd = QUICKER_CONFIG['password']
    uri = f"ws://{host}:{port}/ws"

    try:
        # 建立连接
        # 当前设置：ping_interval=20 启用自动 ping，每 20 秒发送一次心跳
        # 如需禁用自动 ping，可改为 ping_interval=None（防止某些服务端不兼容导致断开）
        # 也可以根据需要开启
        _WS_CONNECTION = await websockets.connect(uri, ping_interval=20, ping_timeout=20)
        console.print(f"    Quicker WebSocket 已连接: {uri}")

        # 3. 认证逻辑
        if pwd:
            MSG_AUTH_REQ = 5
            MSG_AUTH_RESP = 6
            
            auth_payload = {
                "messageType": MSG_AUTH_REQ,
                "data": pwd,
                "serial": 0
            }
            await _WS_CONNECTION.send(json.dumps(auth_payload))
            
            # 等待认证结果
            result = await _WS_CONNECTION.recv()
            resp = json.loads(result)
            
            if resp.get('messageType') == MSG_AUTH_RESP:
                if not resp.get('isSuccess'):
                    console.print(f"    Quicker 认证失败：密码错误")
                    await _WS_CONNECTION.close()
                    _WS_CONNECTION = None
                    return None
                else:
                    console.print("    Quicker 认证成功")
            else:
                console.print(f"    Quicker 认证异常: {result}")
                await _WS_CONNECTION.close()
                _WS_CONNECTION = None
                return None
                
        return _WS_CONNECTION

    except Exception as e:
        console.print(f"    连接 Quicker 失败: {e}")
        _WS_CONNECTION = None
        return None

async def 设置Quicker配置(ip=None, port=None, password=None):
    """
    更新配置（在异步版本中，通常不需要显式调用连接，触发操作时会自动连接，这也是为了方便没有 quicker 的人不至于触发报错）
    """
    global _WS_CONNECTION
    if ip: QUICKER_CONFIG['host'] = ip
    if port: QUICKER_CONFIG['port'] = port
    if password is not None: QUICKER_CONFIG['password'] = password
    
    # 如果配置变了，强制断开现有连接，以便下次操作时使用新配置重连
    if _WS_CONNECTION:
        try:
            await _WS_CONNECTION.close()
        except Exception as e:
            console.print(f"    关闭 Quicker 连接时出错: {e}")
        _WS_CONNECTION = None

async def 触发Quicker操作(动作ID: str):
    """
    使用已建立的连接发送动作指令
    """
    global _WS_CONNECTION, _MSG_SERIAL
    
    ws = await 获取连接()
    if not ws:
        console.print("    无法建立连接，操作取消")
        return

    # 协议常量
    MSG_PUSH = 2
    
    try:
        _MSG_SERIAL += 1
        
        action_payload = {
            "messageType": MSG_PUSH,
            "operation": "action",
            "data": "triggered_by_python", 
            "action": 动作ID,
            "serial": _MSG_SERIAL
        }
        
        await ws.send(json.dumps(action_payload))
        console.print(f"    已发送动作指令: {动作ID}")
        
    except ConnectionClosed:
        console.print("    发送过程中连接断开，尝试重连并重发...")
        # 强制重置连接
        _WS_CONNECTION = None
        ws = await 获取连接()
        if ws:
            try:
                await ws.send(json.dumps(action_payload))
                console.print(f"    重连后发送成功: {动作ID}")
            except Exception as e:
                console.print(f"    重连后发送依然失败: {e}")
    except Exception as e:
        console.print(f"    发送动作失败: {e}")

# --- 测试代码 ---
if __name__ == '__main__':
    async def main():
        console.print(f'\x9b42m-------------开始测试 (Async)---------------\x9b0m')
        
        # 1. 配置
        await 设置Quicker配置(ip="127.0.0.1", port=6655, password="Iloveyou")

        # 2. 触发操作
        await 触发Quicker操作("0d880d7d-c965-43e3-a2e1-ad782a3afdbc") 

        # 模拟保持一段时间，防止立即退出（实际使用中不需要）
        await asyncio.sleep(1)

    try:
        # Windows 上使用 asyncio.run 可能会在结束时报 ProactorEventLoop 错误，这是 Python 3.8+ Windows 的已知行为，通常可忽略
        asyncio.run(main())
    except KeyboardInterrupt:
        # 用户通过 Ctrl+C 主动中断程序，这里忽略异常以实现静默退出
        pass