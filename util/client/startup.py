
import os
from platform import system
from util.client.state import get_state
from util.logger import get_logger
from config import ClientConfig as Config
from util.ui.tray import enable_min_to_tray_with_rectify
from util.client.cleanup import request_exit_from_tray
from util.client.ui import TipsDisplay
from util.client.processing.hotword import get_hotword_manager
from util.llm.llm_handler import init_llm_system
from util.client.audio import AudioStreamManager
from util.client.input import ShortcutHandler
from util.tools.empty_working_set import empty_current_working_set

logger = get_logger('client')

def setup_client_components(base_dir):
    """
    初始化客户端各个组件
    
    Args:
        base_dir: 项目根目录
        
    Returns:
        ClientState: 初始完成的全局状态对象
    """
    state = get_state()
    state.initialize()

    # 1. 托盘
    if Config.enable_tray:
        def restart_audio():
            """重启音频服务回调"""
            if state.stream_manager:
                state.stream_manager.reopen()
                from util.client.ui import TipsDisplay
                # 可以加个提示
                logger.info("用户请求重启音频服务")

        icon_path = os.path.join(base_dir, 'assets', 'icon.ico')
        enable_min_to_tray_with_rectify(
            'CapsWriter Client',
            icon_path,
            logger=logger,
            exit_callback=request_exit_from_tray,
            more_options=[('重启音频服务', restart_audio)]
        )
        logger.info("托盘图标已启用（带纠错记录菜单）")

    # 2. UI 提示
    TipsDisplay.show_mic_tips()

    # 3. 热词
    logger.info("正在加载热词...")
    hotword_manager = get_hotword_manager()
    hotword_manager.load_all()
    hotword_manager.start_file_watcher()

    # 4. LLM
    logger.info("正在初始化 LLM 系统...")
    init_llm_system()
    logger.info("LLM 系统初始化完成")

    # 5. 音频流
    logger.info("正在打开音频流...")
    stream_manager = AudioStreamManager(state)
    state.stream_manager = stream_manager
    stream_manager.open()

    # 6. 快捷键
    logger.info(f"正在绑定快捷键: {Config.shortcut}")
    shortcut_handler = ShortcutHandler(state)
    state.shortcut_handler = shortcut_handler
    shortcut_handler.bind()

    # 7. 内存清理
    if system() == 'Windows':
        empty_current_working_set()

    logger.info("客户端初始化完成，等待语音输入...")
    return state
