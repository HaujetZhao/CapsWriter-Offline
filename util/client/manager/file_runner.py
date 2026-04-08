# coding: utf-8
from pathlib import Path
from . import logger
from util.tools.lifecycle import lifecycle
from config_client import ClientConfig as Config, __version__


class FileRunner:
    """
    文件模式运行器：负责文件转录模式下的逻辑，包括音视频文件的 ASR 转录和字幕文件的时间轴调整。
    """
    def __init__(self, state, ws_manager, resource_manager, files: list[Path]):
        self.state = state
        self.ws_manager = ws_manager
        self.resource_manager = resource_manager
        self.files = files

    async def run(self):
        """文件转录模式主循环 (Coroutine)"""
        from ..transcribe import FileTranscriber, SrtAdjuster
        from ..ui import TipsDisplay
        
        TipsDisplay.show_file_tips()
        
        # 委派公共资源管理 (热词、LLM)
        self.resource_manager.initialize()
        
        logger.info(f"待处理文件: {[str(f) for f in self.files]}")
        
        srt_adjuster = SrtAdjuster()
        
        try:
            for file in self.files:
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
            
            # 关闭连接
            await self.ws_manager.close()
            
            logger.info("所有文件已处理完成")
            
            # 只有在非停机请求下才阻塞等待回车
            if not lifecycle.is_shutting_down:
                input('\n按回车退出\n')

        except Exception as e:
            logger.error(f"文件模式运行异常: {e}", exc_info=True)
            raise
