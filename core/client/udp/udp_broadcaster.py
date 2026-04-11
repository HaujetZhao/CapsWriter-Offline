# coding: utf-8
import socket
from . import logger
from config_client import ClientConfig as Config

def broadcast_output_udp(text: str):
    """
    将识别结果通过 UDP 广播到配置的地址
    """
    if not Config.udp_broadcast or not Config.udp_broadcast_targets:
        return

    message = text.encode('utf-8')
    for addr, port in Config.udp_broadcast_targets:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(message, (addr, port))
                logger.debug(f"UDP 发送输出文本到 {addr}:{port}, 长度: {len(text)}")
        except Exception as e:
            logger.warning(f"UDP 发送输出文本到 {addr}:{port} 失败: {e}")
