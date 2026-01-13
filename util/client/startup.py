
import os
from pathlib import Path
from platform import system
from util.client.state import get_state
from util.logger import get_logger
from config import ClientConfig as Config
from util.ui.tray import enable_min_to_tray
from util.client.cleanup import request_exit_from_tray
from util.client.ui import TipsDisplay
from util.hotword import get_hotword_manager
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
                logger.info("用户请求重启音频")

        def clear_memory():
            """清除 LLM 对话记忆回调"""
            from util.llm.llm_handler import clear_llm_history
            clear_llm_history()
            from util.ui.toast import toast
            toast("清除成功：已清除所有角色的对话历史记录", duration=3000, bg="#075077")

        def add_hotword():
            """添加热词回调"""
            try:
                from util.ui.hotword_menu_handler import on_add_hotword
                on_add_hotword()
            except ImportError as e:
                logger.warning(f"无法导入热词菜单处理器: {e}")

        def add_rectify():
            """添加纠错记录回调"""
            try:
                from util.ui.rectify_menu_handler import on_add_rectify_record
                on_add_rectify_record()
            except ImportError as e:
                logger.warning(f"无法导入纠错菜单处理器: {e}")

        def copy_last_result():
            """复制上一次输出结果回调"""
            text = state.last_output_text
            if text:
                from util.llm.llm_clipboard import copy_to_clipboard
                copy_to_clipboard(text)
            #     from util.ui.toast import toast
            #     toast("已复制上次输出结果", duration=2000)
            # else:
            #     from util.ui.toast import toast
            #     toast("复制失败：尚无输出结果", duration=2000, bg="#CC3333")

        icon_path = os.path.join(base_dir, 'assets', 'icon.ico')
        enable_min_to_tray(
            'CapsWriter Client',
            icon_path,
            logger=logger,
            exit_callback=request_exit_from_tray,
            more_options=[
                ('📋 复制结果', copy_last_result),
                ('✨ 添加热词', add_hotword),
                ('🛠️ 添加纠错', add_rectify),
                ('🧹 清除记忆', clear_memory),
                ('🔄 重启音频', restart_audio),
            ]
        )
        logger.info("托盘图标已启用")

    # 2. UI 提示
    TipsDisplay.show_mic_tips()

    # 3. 热词
    logger.info("正在加载热词...")
    hotword_files = {
        'hot': Path('hot.txt'),
        'rule': Path('hot-rule.txt'),
        'rectify': Path('hot-rectify.txt'),
    }
    hotword_manager = get_hotword_manager(
        hotword_files=hotword_files,
        threshold=Config.hot_thresh,
        similar_threshold=Config.hot_similar,
        rectify_threshold=Config.hot_rectify
    )
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
