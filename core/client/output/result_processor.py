import pyperclip
import keyboard
from core.utils.logger import logger
from core.ui.recording_indicator import RecordingIndicator  # 新增导入


class ResultProcessor:
    def __init__(self, config):
        self.config = config
        self.mode = config.get("output_mode", "typing")  # typing / clipboard
        self._indicator = RecordingIndicator()  # 新增指示器实例

    def handle_result(self, result, task_id):
        text = result.get("text", "").strip()
        if not text:
            logger.info(f"Task {task_id} empty result")
            self._indicator.hide()  # 新增：空结果隐藏指示器
            return

        logger.info(f"Task {task_id} result: {text}")

        try:
            if self.mode == "clipboard":
                pyperclip.copy(text)
                logger.info("Copied to clipboard")
            else:
                keyboard.write(text)
                logger.info("Typed text")
        except Exception as e:
            logger.error(f"Output error: {e}")
        finally:
            self._indicator.hide()  # 新增：处理完成后隐藏指示器
