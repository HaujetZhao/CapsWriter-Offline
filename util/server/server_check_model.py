# coding: utf-8
"""
模型检查模块

检查配置的语音模型文件是否存在，如果不存在则提供下载链接。
"""

import sys
from pathlib import Path

from config_server import ServerConfig as Config
from config_server import ModelPaths, ModelDownloadLinks
from util.server.server_cosmic import console
from util.common.lifecycle import lifecycle
from . import logger



def check_model() -> None:
    """
    根据配置的模型类型检查所需的模型文件是否存在
    
    如果模型文件不存在，显示错误信息和下载链接后退出程序。
    
    Raises:
        SystemExit: 当模型类型不支持或模型文件缺失时退出
    """
    model_type = Config.model_type.lower()
    logger.debug(f"检查模型文件, 类型: {model_type}")

    # 根据模型类型确定需要检查的文件
    if model_type == 'fun_asr_nano':
        required_files = {
            'Fun-ASR-Nano-GGUF 模型文件': [
                ModelPaths.fun_asr_nano_gguf_encoder_adaptor,
                ModelPaths.fun_asr_nano_gguf_ctc,
                ModelPaths.fun_asr_nano_gguf_llm_decode,
                ModelPaths.fun_asr_nano_gguf_token,
            ]
        }
    elif model_type == 'sensevoice':
        required_files = {
            'SenseVoice 模型文件': [
                ModelPaths.sensevoice_model,
                ModelPaths.sensevoice_tokens,
            ]
        }
    elif model_type == 'paraformer':
        required_files = {
            'Paraformer 模型文件': [
                ModelPaths.paraformer_model,
                ModelPaths.paraformer_tokens,
            ],
            '标点模型文件': [
                ModelPaths.punc_model_dir,
            ]
        }
    else:
        error_msg = f"不支持的模型类型: {Config.model_type}"
        logger.error(error_msg)
        console.print(f'''
    [bold red]不支持的模型类型：{Config.model_type}[/bold red]

    请在 config_server.py 中将 ServerConfig.model_type 设置为：
    - 'fun_asr_nano'
    - 'sensevoice'
    - 'paraformer'

        ''', style='bright_red')
        input('按回车退出')
        lifecycle.cleanup()
        sys.exit(1)

    # 检查所有必需的文件
    missing_files = []
    for category, files in required_files.items():
        for file_path in files:
            if not file_path.exists():
                missing_files.append((category, file_path))
                logger.warning(f"模型文件缺失: {file_path}")

    # 如果有缺失的文件，显示错误信息并提供下载链接
    if missing_files:
        error_msg = f'\n    [bold red]未能找到模型文件[/bold red]\n\n'
        for category, file_path in missing_files:
            error_msg += f'    [{category}]\n'
            error_msg += f'    未找到：{file_path}\n\n'

        error_msg += f'    当前配置的模型类型：[bold yellow]{model_type}[/bold yellow]\n\n'

        # 提供统一下载页面链接
        error_msg += f'    [cyan]请前往模型发布页下载缺失文件：[/cyan]\n'
        error_msg += f'    [cyan]{ModelDownloadLinks.models_page}[/cyan]\n\n'

        error_msg += f'    下载后请根据发布页说明，解压到：[cyan]{ModelPaths.model_dir}[/cyan]\n'
        error_msg += '    \n'
        
        logger.error(f"模型文件检查失败，共 {len(missing_files)} 个文件缺失")
        console.print(error_msg)
        input('按回车退出')
        lifecycle.cleanup()
        sys.exit(1)

    # 所有检查通过
    logger.info(f"模型文件检查通过 ({model_type})")
    console.print(f'[green4]模型文件检查通过 ({model_type})', end='\n\n')
