# coding: utf-8
"""
CapsWriter Offline 客户端主程序门面类 (Facade)

采用外观模式统一管理音频流 (AudioStreamManager)、
识别结果处理 (ResultProcessor) 和快捷键管理 (ShortcutManager)。
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from platform import system

from util.client.state import get_state
from util.logger import setup_logger
from . import logger
from config_client import ClientConfig as Config, __version__
from util.tools.lifecycle import lifecycle
from util.client.cleanup import cleanup_client_resources, request_exit_from_tray
from .manager import ResourceManager, HardwareManager


class CapsWriterClient:
    """
    CapsWriter 客户端门面类
    
    管理的外部接口简洁：start()。
    """
    def __init__(self, base_dir: str = None):
        # 1. 确定工作目录
        self.base_dir = base_dir or os.getcwd()
        if not os.path.exists(self.base_dir):
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        # 2. 初始化核心状态单例 (基础设施层)
        self.state = get_state()
        self.version = __version__
        self.log_level = Config.log_level
        self._main_task = None

        # 3. 初始化各管理器 (职责下放)
        self.resource_manager = ResourceManager(self.state)
        self.hardware_manager = HardwareManager(self.state)

    def _setup_logging(self):
        """重新配置主日志级别"""
        setup_logger('client', level=self.log_level)

    def _setup_tray(self):
        """
        初始化系统托盘图标
        """
        if not Config.enable_tray:
            return

        try:
            from util.client.ui import enable_min_to_tray, toast
        except ImportError as e:
            logger.warning(f"托盘模块导入失败，跳过托盘功能: {e}")
            return

        def restart_audio():
            if self.state.stream_manager:
                self.state.stream_manager.reopen()
                logger.info("用户请求重启音频")

        def clear_memory():
            from util.client.llm.llm_handler import clear_llm_history
            clear_llm_history()
            toast("清除成功：已清除所有角色的对话历史记录", duration=3000, bg="#075077")

        def add_hotword():
            try:
                from util.client.ui import on_add_hotword
                on_add_hotword()
            except ImportError as e:
                logger.warning(f"无法导入热词菜单处理器: {e}")

        def add_rectify():
            try:
                from util.client.ui import on_add_rectify_record
                on_add_rectify_record()
            except ImportError as e:
                logger.warning(f"无法导入纠错菜单处理器: {e}")

        def add_context():
            try:
                from util.client.ui import on_edit_context
                on_edit_context()
            except ImportError as e:
                logger.warning(f"无法导入上下文菜单处理器: {e}")

        def copy_last_result():
            text = self.state.last_output_text
            if text:
                from util.client.llm.llm_clipboard import copy_to_clipboard
                copy_to_clipboard(text)

        icon_path = os.path.join(self.base_dir, 'assets', 'icon.ico')
        enable_min_to_tray(
            'CapsWriter Client',
            icon_path,
            exit_callback=request_exit_from_tray,
            more_options=[
                ('📋 复制结果', copy_last_result),
                ('📝 上下文', add_context),
                ('✨ 添加热词', add_hotword),
                ('🛠️ 添加纠错', add_rectify),
                ('🧹 清除记忆', clear_memory),
                ('🔄 重启音频', restart_audio),
            ]
        )
        logger.info("托盘图标已启用")

    def _setup_common(self):
        """
        初始化客户端基础环境 (双模共有)
        """
        # 1. 基础状态启动
        self.state.initialize()
        
        # 2. 日志
        self._setup_logging()

        # 3. 委派公共资源管理 (热词、LLM)
        self.resource_manager.initialize()

    def _setup_mic_resources(self):
        """
        初始化麦克风模式特有资源 (音频硬件、快捷键、UI 托盘)
        """
        # 1. 托盘
        self._setup_tray()

        # 2. UI 提示
        from util.client.ui import TipsDisplay
        TipsDisplay.show_mic_tips()

        # 3. 委派硬件资源管理 (音频、快捷键、UDP)
        self.hardware_manager.setup_mic_resources()

    def _check_macos_permissions(self):
        """检查 MacOS 权限设置 (类方法移入)"""
        if system() == 'Darwin' and not sys.argv[1:]:
            if os.getuid() != 0:
                print('在 MacOS 上需要以管理员启动客户端才能监听键盘活动，请 sudo 启动')
                input('按回车退出')
                sys.exit(1)
            else:
                os.umask(0o000)

    async def _run_mic_mode(self):
        """
        麦克风模式主循环 (Coroutine)
        
        负责编排识别处理器和退出信号的监控。
        """
        # 确保硬件资源已就绪
        self._setup_mic_resources()
        
        from util.client.output import ResultProcessor
        
        logger.info("=" * 50)
        logger.info("CapsWriter Offline Client 正在启动（麦克风模式）")
        logger.info(f"版本: {self.version}")
        logger.info(f"日志级别: {self.log_level}")

        try:
            self.processor = ResultProcessor(self.state)
            self.state.processor = self.processor # 注入状态以便清理

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

    async def _run_file_mode(self, files: list[Path]):
        """
        文件转录模式主循环 (Coroutine)
        
        Args:
            files: 待处理的文件列表
        """
        from util.client.transcribe import FileTranscriber, SrtAdjuster
        from util.client.ui import TipsDisplay
        
        logger.info("=" * 50)
        logger.info("CapsWriter Offline Client 正在启动（文件转录模式）")
        logger.info(f"版本: {self.version}")
        logger.info(f"日志级别: {self.log_level}")
        logger.info(f"待处理文件: {[str(f) for f in files]}")
        
        TipsDisplay.show_file_tips()
        
        srt_adjuster = SrtAdjuster()
        
        try:
            for file in files:
                if lifecycle.is_shutting_down:
                    break

                logger.info(f"正在处理文件: {file}")
                
                # 情况 1：文本类文件，执行 SRT 时间轴调整
                if file.suffix.lower() in ['.txt', '.json', '.srt', '.vtt']:
                    srt_adjuster.adjust(file)
                # 情况 2：媒体文件，执行 ASR 识别转录
                else:
                    transcriber = FileTranscriber(self.state, file)
                    if await transcriber.check():
                        await transcriber.send()
                        await transcriber.receive()
                
                logger.info(f"文件处理完成: {file}")
            
            # 关闭残结
            if self.state.websocket:
                await self.state.websocket.close()
                self.state.websocket = None
            
            logger.info("所有文件已处理完成")
            
            # 只有在非停机请求下才阻塞等待回车
            if not lifecycle.is_shutting_down:
                input('\n按回车退出\n')

        except Exception as e:
            logger.error(f"文件模式运行异常: {e}", exc_info=True)
            raise

    async def start(self):
        """
        启动客户端 (唯一入口)
        
        自动根据命令行参数识别模式。
        """
        # 0. MacOS 权限检查
        self._check_macos_permissions()
        
        # 1. 注册全局清理函数
        lifecycle.register_on_shutdown(cleanup_client_resources)
        
        # 2. 初始化生命周期
        lifecycle.initialize(logger=logger, exit_on_signal=True)
        
        # 3. 基础环境初始化 (双模共有)
        self._setup_common()
        
        # 4. 根据参数进入不同模式
        files = [Path(f) for f in sys.argv[1:] if os.path.exists(f)]
        
        try:
            if files:
                # 文件转录模式
                await self._run_file_mode(files)
            else:
                # 麦克风实时模式
                await self._run_mic_mode()
            
            # 正常完成清理
            lifecycle.cleanup()
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("用户请求停止...")
            lifecycle.cleanup()
        except Exception as e:
            logger.error(f"客户端运行出错: {e}", exc_info=True)
            lifecycle.cleanup()
            raise
