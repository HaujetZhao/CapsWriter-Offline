import time
import threading
import queue
from core.client.audio.recorder import AudioRecorder
from core.client.audio.processor import AudioProcessor
from core.client.output.result_processor import ResultProcessor
from core.utils.logger import logger
from core.ui.recording_indicator import RecordingIndicator  # 新增导入


class Task:
    def __init__(self, task_id, config):
        self.task_id = task_id
        self.config = config
        self.recorder = AudioRecorder(config)
        self.processor = AudioProcessor(config)
        self.result_processor = ResultProcessor(config)
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.is_canceled = False
        self.recording = False
        self._thread = None
        self._indicator = RecordingIndicator()  # 新增指示器实例

    def start_recording(self):
        if self.recording:
            return
        logger.info(f"Task {self.task_id} start recording")
        self.recording = True
        self.is_canceled = False
        self.recorder.start()
        self._indicator.show_recording()  # 新增：显示录音状态
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_recording(self):
        if not self.recording:
            return
        logger.info(f"Task {self.task_id} stop recording")
        self.recording = False
        self.recorder.stop()
        self._indicator.show_recognizing()  # 新增：切换到识别状态

    def cancel(self):
        logger.info(f"Task {self.task_id} canceled")
        self.is_canceled = True
        self.recording = False
        self.recorder.stop()
        self.audio_queue.queue.clear()
        self._indicator.hide()  # 新增：隐藏指示器

    def _run(self):
        try:
            while self.recording or not self.audio_queue.empty():
                try:
                    chunk = self.recorder.read_chunk(timeout=0.1)
                    if chunk:
                        self.audio_queue.put(chunk)
                except queue.Empty:
                    continue

            if self.is_canceled:
                return

            audio_data = b""
            while not self.audio_queue.empty():
                audio_data += self.audio_queue.get()

            if len(audio_data) == 0:
                self._indicator.hide()  # 新增：无音频则隐藏
                return

            result = self.processor.process(audio_data)
            if result and not self.is_canceled:
                self.result_processor.handle_result(result, self.task_id)

        except Exception as e:
            logger.error(f"Task {self.task_id} error: {e}")
        finally:
            # 指示器隐藏移到 result_processor 中处理，确保结果输出后再消失
            pass
