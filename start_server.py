# coding: utf-8
import argparse
from multiprocessing import freeze_support

from config_server import ServerConfig


SUPPORTED_MODELS = (
    'qwen_asr',
    'fun_asr_nano',
    'sensevoice',
    'paraformer',
)


def parse_server_args(argv=None):
    parser = argparse.ArgumentParser(description='Start the CapsWriter server')
    parser.add_argument(
        '--model',
        choices=SUPPORTED_MODELS,
        help='Override ServerConfig.model_type for this launch',
    )
    return parser.parse_args(argv)


def configure_model(model_type):
    if model_type is not None:
        ServerConfig.model_type = model_type


def main(argv=None):
    args = parse_server_args(argv)
    configure_model(args.model)

    # 延迟导入，确保所有服务端模块读取到命令行覆盖后的配置。
    from core.server.app import CapsWriterServer

    CapsWriterServer().start()

if __name__ == '__main__':
    # 启用对 PyInstaller 打包后的多进程支持
    freeze_support()
    main()