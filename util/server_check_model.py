import sys
from pathlib import Path

from config import ModelPaths, ServerConfig as Config
from util.server_cosmic import console


def check_model():
    """
    根据配置的模型类型检查所需的模型文件是否存在
    """
    model_type = Config.model_type.lower()

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
        console.print(f'''
    不支持的模型类型：{Config.model_type}

    请在 config.py 中将 ServerConfig.model_type 设置为：
    - 'funasr_nano'
    - 'sensevoice'
    - 'paraformer'

        ''', style='bright_red')
        input('按回车退出')
        sys.exit()

    # 检查所有必需的文件
    missing_files = []
    for category, files in required_files.items():
        for file_path in files:
            if not file_path.exists():
                missing_files.append((category, file_path))

    # 如果有缺失的文件，显示错误信息并退出
    if missing_files:
        error_msg = f'\n    未能找到模型文件\n\n'
        for category, file_path in missing_files:
            error_msg += f'    [{category}]\n'
            error_msg += f'    未找到：{file_path}\n\n'

        error_msg += f'    请下载模型并放置到：{ModelPaths.model_dir}\n'
        error_msg += f'    当前配置的模型类型：{model_type}\n\n'
        error_msg += '    按回车退出\n    '

        console.print(error_msg, style='bright_red')
        input()
        sys.exit()

    # 所有检查通过
    console.print(f'[green4]模型文件检查通过 ({model_type})', end='\n\n')
