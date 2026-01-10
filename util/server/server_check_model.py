# coding: utf-8
"""
模型检查模块

检查配置的语音模型文件是否存在，如果不存在则提供下载链接。
"""

import sys
from pathlib import Path

from config import ModelPaths, ServerConfig as Config, ModelDownloadLinks
from util.server.server_cosmic import console
from util.logger import get_logger

# 日志记录器
logger = get_logger('server')


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
    if model_type == 'funasr_nano':
        required_files = {
            'FunASR-nano 模型文件': [
                ModelPaths.funasr_nano_tokenizer,
                ModelPaths.funasr_nano_encoder_adaptor,
                ModelPaths.funasr_nano_embedding,
                ModelPaths.funasr_nano_llm_prefill,
                ModelPaths.funasr_nano_llm_decode,
            ]
        }
        download_link = ModelDownloadLinks.funasr_nano
        model_name = "FunASR-nano"
    elif model_type == 'sensevoice':
        required_files = {
            'SenseVoice 模型文件': [
                ModelPaths.sensevoice_model,
                ModelPaths.sensevoice_tokens,
            ]
        }
        download_link = ModelDownloadLinks.sensevoice
        model_name = "SenseVoice"
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
        download_link = ModelDownloadLinks.paraformer
        model_name = "Paraformer"
        punct_download_link = ModelDownloadLinks.punct
    else:
        error_msg = f"不支持的模型类型: {Config.model_type}"
        logger.error(error_msg)
        console.print(f'''
    [bold red]不支持的模型类型：{Config.model_type}[/bold red]

    请在 config.py 中将 ServerConfig.model_type 设置为：
    - 'funasr_nano'
    - 'sensevoice'
    - 'paraformer'

        ''', style='bright_red')
        input('按回车退出')
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

        # 提供下载链接
        if download_link:
            error_msg += f'    [cyan]下载链接：{download_link}[/cyan]\n\n'
        else:
            error_msg += f'    [dim]暂无官方下载链接，请手动下载 {model_name} 模型[/dim]\n\n'

        # 如果是 Paraformer，还需要标点模型链接
        if model_type == 'paraformer' and missing_files[0][0] == '标点模型文件':
            if punct_download_link:
                error_msg += f'    [cyan]标点模型下载链接：{punct_download_link}[/cyan]\n\n'

        error_msg += f'    下载后请解压到：[cyan]{ModelPaths.model_dir}[/cyan]\n'
        error_msg += '    \n    按回车退出\n    '

        logger.error(f"模型文件检查失败，共 {len(missing_files)} 个文件缺失")
        console.print(error_msg)
        input()
        sys.exit(1)

    # 所有检查通过
    logger.info(f"模型文件检查通过 ({model_type})")
    console.print(f'[green4]模型文件检查通过 ({model_type})', end='\n\n')
