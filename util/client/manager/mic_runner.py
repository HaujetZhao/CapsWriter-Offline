# coding: utf-8
import asyncio
from . import logger
from util.tools.lifecycle import lifecycle
from config_client import ClientConfig as Config, __version__


class MicRunner:
    """
    麦克风模式运行器：负责麦克风模式下的资源初始化、识别处理器循环及生命周期监控。
    """
    def __init__(self, state, ws_manager, hardware_manager, tray_manager, resource_manager):
        self.state = state
        self.ws_manager = ws_manager
        self.hardware_manager = hardware_manager
        self.tray_manager = tray_manager
        self.resource_manager = resource_manager
        self.processor = None

    def _setup_resources(self):
        """初始化麦克风模式特有资源 (音频硬件、快捷键、UI 托盘)"""
        # 1. 托盘
        self.tray_manager.setup_tray()

        # 2. UI 提示
        from ..ui import TipsDisplay
        TipsDisplay.show_mic_tips()

        # 3. 委派公共资源管理 (热词、LLM)
        self.resource_manager.initialize()

        # 3. 委派硬件资源管理 (音频、快捷键、UDP)
        self.hardware_manager.setup_mic_resources()

    async def run(self):
        """麦克风模式主循环 (Coroutine)"""
        # 确保硬件资源已就绪
        self._setup_resources()
        
        from ..output import ResultProcessor
        
        logger.info("=" * 50)
        logger.info("CapsWriter Offline Client 正在启动（麦克风模式）")
        logger.info(f"版本: {__version__}")
        logger.info(f"日志级别: {Config.log_level}")

        try:
            self.processor = ResultProcessor(self.state, self.ws_manager)

            # 主循环：只要没收到退出信号，就一直运行
            while not lifecycle.is_shutting_down:
                # 1. 创建处理任务 (WebSocket 接收与结果处理)
                process_task = asyncio.create_task(self.processor.process_loop())
                # 2. 创建等待退出任务
                wait_shutdown = asyncio.create_task(lifecycle.wait_for_shutdown())

                done, pending = await asyncio.wait(
                    [process_task, wait_shutdown],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # 情况 A：监听到停机信号
                if wait_shutdown in done:
                    logger.info("麦克风模式检测到停机信号，正在取消识别任务...")
                    if not process_task.done():
                        process_task.cancel()
                        try:
                            await process_task
                        except asyncio.CancelledError:
                            pass
                    break
                
                # 情况 B：处理任务自行结束（可能是断开连接或报错）
                if process_task in done:
                    # 再次检查是否是因为 lifecycle 导致的退出
                    if lifecycle.is_shutting_down:
                        break
                    
                    try:
                        # 获取任务结果，如有异常会在此抛出
                        await process_task
                    except Exception as e:
                        logger.error(f"识别处理循环发生异常: {e}")
                        # 失败后稍等片刻再尝试，防止死循环刷日志
                        await asyncio.sleep(2)
                    
                    # 自动重启（对于麦克风模式，我们希望它在断连后能自动恢复）
                    if not lifecycle.is_shutting_down:
                        logger.info("识别循环已结束，正在尝试重启...")

        except asyncio.CancelledError:
            logger.info("麦克风模式主任务已取消")
            raise
        except Exception as e:
            logger.error(f"麦克风模式运行异常: {e}", exc_info=True)
            raise
