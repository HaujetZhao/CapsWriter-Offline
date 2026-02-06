
import os
from pathlib import Path
from platform import system
from util.client.state import get_state
from . import logger
from config_client import ClientConfig as Config
from util.client.cleanup import request_exit_from_tray
from util.client.ui import TipsDisplay
from util.hotword import get_hotword_manager
from util.llm.llm_handler import init_llm_system
from util.client.audio import AudioStreamManager
from util.client.shortcut.shortcut_config import Shortcut
from util.client.shortcut.shortcut_manager import ShortcutManager
from util.tools.empty_working_set import empty_current_working_set



def _setup_tray(state, base_dir):
    """
    初始化托盘图标（延迟导入，支持无 GUI 环境）
    """
    try:
        from util.client.ui import enable_min_to_tray
    except ImportError as e:
        logger.warning(f"托盘模块导入失败，跳过托盘功能: {e}")
        return

    def restart_audio():
        if state.stream_manager:
            state.stream_manager.reopen()
            logger.info("用户请求重启音频")

    def clear_memory():
        from util.llm.llm_handler import clear_llm_history
        clear_llm_history()
        from util.client.ui import toast
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
        text = state.last_output_text
        if text:
            from util.llm.llm_clipboard import copy_to_clipboard
            copy_to_clipboard(text)

    import os
    icon_path = os.path.join(base_dir, 'assets', 'icon.ico')
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
        _setup_tray(state, base_dir)

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

    # 6. 快捷键管理器（统一管理键盘和鼠标快捷键）
    # 从 Config.shortcuts 列表创建 Shortcut 对象
    shortcuts = [Shortcut(**sc) for sc in Config.shortcuts]
    logger.info(f"正在初始化快捷键管理器，共 {len(shortcuts)} 个快捷键")

    shortcut_manager = ShortcutManager(state, shortcuts)
    state.shortcut_manager = shortcut_manager
    shortcut_manager.start()

    # 为了兼容性，同时保留旧的 shortcut_handler 引用
    state.shortcut_handler = shortcut_manager

    # 7. UDP 控制（可选）
    if Config.udp_control:
        from util.client.udp.udp_control import UDPController
        logger.info(f"正在启用 UDP 控制，端口: {Config.udp_control_port}")
        udp_controller = UDPController(shortcut_manager)
        state.udp_controller = udp_controller
        udp_controller.start()

    # 9. 内存清理
    if system() == 'Windows':
        empty_current_working_set()

    logger.info("客户端初始化完成，等待语音输入...")
    return state

