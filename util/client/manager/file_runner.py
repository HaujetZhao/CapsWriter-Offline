# coding: utf-8
from . import logger
from pathlib import Path
from util.tools.lifecycle import lifecycle


class FileRunner:
    """
    文件模式运行器：负责文件转录模式下的逻辑，包括音视频文件的 ASR 转录和字幕文件的时间轴调整。
    """
    def __init__(self, state, files: list[Path], version, log_level):
        self.state = state
        self.files = files
        self.version = version
        self.log_level = log_level

    async def run(self):
        """文件转录模式主循环 (Coroutine)"""
        from ..transcribe import FileTranscriber, SrtAdjuster
        from ..ui import TipsDisplay
        
        logger.info("=" * 50)
        logger.info("CapsWriter Offline Client 正在启动（文件转录模式）")
        logger.info(f"版本: {self.version}")
        logger.info(f"日志级别: {self.log_level}")
        logger.info(f"待处理文件: {[str(f) for f in self.files]}")
        
        TipsDisplay.show_file_tips()
        
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
