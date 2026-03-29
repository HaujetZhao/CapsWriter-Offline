"""
LLM 对话记录到 Markdown

将用户输入和 LLM 润色结果保存到 Markdown 文件
"""
import time
from pathlib import Path
from os import makedirs


# LLM 对话记录的文件头
header_llm_md = r'''# LLM 对话记录

'''


def create_llm_md(file_md: Path):
    """创建 LLM 对话记录文件"""
    with open(file_md, 'w', encoding="utf-8") as f:
        f.write(header_llm_md)


def write_llm_md(input_text: str, polished_text: str, role_name: str, time_start: float, file_audio: Path = None):
    """
    写入 LLM 对话到 Markdown 文件

    Args:
        input_text: 用户输入（识别结果）
        polished_text: LLM 润色后的文本
        role_name: 角色名称
        time_start: 开始时间戳
        file_audio: 音频文件路径（可选）
    """
    # 格式化时间
    time_year = time.strftime('%Y', time.localtime(time_start))
    time_month = time.strftime('%m', time.localtime(time_start))
    time_day = time.strftime('%d', time.localtime(time_start))
    time_hms = time.strftime('%H:%M:%S', time.localtime(time_start))

    # 创建目录: 年份/月份/（与日记记录相同位置）
    folder_path = Path() / time_year / time_month
    makedirs(folder_path, exist_ok=True)

    # 文件名: 日期-角色.md（如果有角色名，默认角色使用 '默认'）
    role_name_for_file = role_name if role_name else '默认'
    file_md = folder_path / f'{time_day}-{role_name_for_file}.md'

    # 确保 md 文件存在
    if not file_md.exists():
        create_llm_md(file_md)

    # 写入对话记录
    with open(file_md, 'a', encoding="utf-8") as f:
        # 标题：时间 + 音频链接（如果有）
        if file_audio:
            audio_filename = file_audio.name
            f.write(f'#### [[{time_hms}]](({audio_filename})\n\n')
        else:
            f.write(f'#### [{time_hms}]\n\n')

        # 用户输入
        f.write(f'**输入**：{input_text}\n\n')

        # LLM 输出
        f.write(f'**输出**：{polished_text}\n\n')

        # 分隔线
        f.write('---\n\n')
