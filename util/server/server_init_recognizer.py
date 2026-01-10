import time
import sherpa_onnx
from multiprocessing import Queue
import signal
from platform import system
from config import ServerConfig as Config
from config import ParaformerArgs, ModelPaths, SenseVoiceArgs, FunASRNanoArgs
from util.server.server_check_model import check_model
from util.server.server_cosmic import console
from util.server.server_recognize import recognize
from util.tools.empty_working_set import empty_current_working_set
from util.logger import get_logger

# 获取日志记录器
logger = get_logger('server')





def init_recognizer(queue_in: Queue, queue_out: Queue, sockets_id):
    logger.info("识别子进程启动")
    logger.debug(f"系统平台: {system()}")

    # Ctrl-C 退出
    signal.signal(signal.SIGINT, lambda signum, frame: exit())

    # 导入模块
    with console.status("载入模块中…", spinner="bouncingBall", spinner_style="yellow"):
        import sherpa_onnx
    console.print('[green4]模块加载完成', end='\n\n')
    logger.info("Sherpa-ONNX 模块加载完成")

    # 载入语音模型
    console.print('[yellow]语音模型载入中', end='\r'); t1 = time.time()
    logger.info(f"开始加载语音模型，类型: {Config.model_type}")

     # 检查模型文件
    check_model()

    # 根据配置选择模型类型
    model_type = Config.model_type.lower()
    try:
        if model_type == 'funasr_nano':
            logger.debug("使用 FunASR-Nano 模型")
            recognizer = sherpa_onnx.OfflineRecognizer.from_funasr_nano(
                **{key: value for key, value in FunASRNanoArgs.__dict__.items() if not key.startswith('_')}
            )
        elif model_type == 'sensevoice':
            logger.debug("使用 SenseVoice 模型")
            recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                **{key: value for key, value in SenseVoiceArgs.__dict__.items() if not key.startswith('_')}
            )
        elif model_type == 'paraformer':
            logger.debug("使用 Paraformer 模型")
            recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                **{key: value for key, value in ParaformerArgs.__dict__.items() if not key.startswith('_')}
            )
        else:
            error_msg = f"不支持的模型类型: {Config.model_type}，请选择 'funasr_nano'、'sensevoice' 或 'paraformer'"
            logger.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"模型加载失败: {e}", exc_info=True)
        raise

    console.print(f'[green4]语音模型载入完成 ({model_type})', end='\n\n')
    logger.info(f"语音模型加载完成 ({model_type})，耗时: {time.time() - t1:.2f}s")

    # 载入标点模型（仅 Paraformer 需要）
    punc_model = None
    if model_type == 'paraformer':
        logger.info("开始加载标点模型")
        console.print('[yellow]标点模型载入中', end='\r')
        config = sherpa_onnx.OfflinePunctuationConfig(
            model=sherpa_onnx.OfflinePunctuationModelConfig(
                ct_transformer=ModelPaths.punc_model_dir.as_posix()
            ),
        )
        punc_model = sherpa_onnx.OfflinePunctuation(config)
        console.print(f'[green4]标点模型载入完成', end='\n\n')
        logger.info("标点模型加载完成")

    console.print(f'模型加载耗时 {time.time() - t1 :.2f}s', end='\n\n')

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()
        logger.debug("已清空物理内存工作集")

    queue_out.put(True)  # 通知主进程加载完了
    logger.info("识别器初始化完成，开始处理任务")

    while True:
        # 从队列中获取任务消息
        # 阻塞最多1秒，便于中断退出
        try:
            task = queue_in.get(timeout=1)
        except:
            continue

        # 检查退出信号
        if task is None:
            logger.info("收到退出信号，识别子进程正在停止...")
            break

        if task.socket_id not in sockets_id:    # 检查任务所属的连接是否存活
            logger.debug(f"任务所属连接已断开，跳过处理，任务ID: {task.task_id}")
            continue

        result = recognize(recognizer, punc_model, task)   # 执行识别
        queue_out.put(result)      # 返回结果

    # 清理完成
    logger.info("识别子进程已退出")
