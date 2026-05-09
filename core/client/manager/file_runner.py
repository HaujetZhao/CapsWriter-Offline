# coding: utf-8
from __future__ import annotations
from pathlib import Path
from . import logger
from config_client import ClientConfig as Config, __version__


class FileRunner:
    """
    文件模式运行器：负责文件转录模式下的逻辑，包括音视频文件的 ASR 转录和字幕文件的时间轴调整。
    """
    def __init__(self, app, files: list[Path]):
        self.app = app
        self.files = files

    @property
    def state(self):
        return self.app.state

    @property
    def ws_manager(self):
        return self.app.ws

    async def run(self):
        """文件转录模式主循环 (Coroutine)"""
        from ..transcribe import FileTranscriber, SrtAdjuster
        from ..ui import TipsDisplay
        
        TipsDisplay.show_file_tips()
        
        logger.info(f"待处理文件: {[str(f) for f in self.files]}")
        
        
        # 加载热词资源
        self.app.hotword.start()

        try:
            for file in self.files:

                logger.info(f"正在处理文件: {file}")
                
                # 情况 1：文本类文件，执行 SRT 时间轴调整
                if file.suffix.lower() in ['.txt', '.json', '.srt', '.vtt']:
                    srt_adjuster = SrtAdjuster()
                    srt_adjuster.adjust(file)
                    
                # 情况 2：媒体文件，执行 ASR 识别转录
                else:
                    transcriber = FileTranscriber(self.app, file)
                    if await transcriber.check():
                        await transcriber.send()
                        await transcriber.receive()
                        await transcriber.close()
                
                logger.info(f"文件处理完成: {file}")
            
            logger.info("所有文件已处理完成")
            
            input('\n按回车退出\n')

        except Exception as e:
            logger.error(f"文件模式运行异常: {e}", exc_info=True)
            raise
        finally:
            self.app.hotword.stop()
