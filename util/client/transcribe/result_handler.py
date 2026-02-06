# coding: utf-8
import re
import json
from pathlib import Path
from typing import Dict, Any

from config_client import ClientConfig as Config
from util.tools import srt_from_txt
from . import logger

class ResultHandler:
    """结果处理器：负责文本格式化和文件保存"""

    @staticmethod
    def smart_split(text: str) -> str:
        """
        智能分行功能
        1. 保留标点符号
        2. 避免在逗号处切分过短的句子
        3. 英文标点需后跟空格才切分（避免 3.14 被切分）
        """
        # 使用捕获组保留标点，英文标点需后跟空白符或结尾
        parts = re.split(r'([，。？]|[.,?!](?:\s+|$))', text)
        lines = []
        buffer = ""
        
        # 强标点（必须换行）
        strong_punct = {'。', '？', '.', '?', '!'}
        punct_chars = set('，。？,.\?!')
        
        for part in parts:
            clean_part = part.strip()
            # 如果是标点符号（长度为1且在列表中）
            if clean_part and clean_part in punct_chars and len(clean_part) == 1:
                buffer += part
                is_strong = clean_part in strong_punct
                # 如果是强标点，或者缓冲区够长，就换行
                if is_strong or len(buffer) > 15:
                    lines.append(buffer)
                    buffer = ""
            else:
                # 是文本
                buffer += part
        
        if buffer:
            lines.append(buffer)

        # 去除每行末尾的标点
        final_lines = []
        for line in lines:
            line = line.strip()
            # 循环去除结尾的标点
            while line and line[-1] in punct_chars:
                line = line[:-1].strip()
            if line:
                final_lines.append(line)
            
        return "\n".join(final_lines)

    @classmethod
    def save_results(cls, file: Path, message: Dict[str, Any]) -> str:
        """
        保存转录结果到文件
        
        Returns:
            split_text: 切分后的文本（用于显示）
        """
        text_display = message['text']
        text_accu = message.get('text_accu', message['text'])
        text_split = cls.smart_split(text_accu)
        timestamps = message['timestamps']
        tokens = message['tokens']
        
        # 文件名
        json_filename = file.with_suffix('.json')
        txt_filename = file.with_suffix('.txt')
        merge_filename = file.with_suffix('.merge.txt')
        
        # 1. 保存 merge.txt
        if Config.file_save_merge:
            with open(merge_filename, 'w', encoding='utf-8') as f:
                f.write(text_accu)
            logger.debug(f"保存合并文本: {merge_filename}")

        # 2. 保存 txt
        if Config.file_save_txt:
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(text_split)
            logger.debug(f"保存切分文本: {txt_filename}")

        # 3. 保存 json
        if Config.file_save_json:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump({'timestamps': timestamps, 'tokens': tokens}, f, ensure_ascii=False)
            logger.debug(f"保存 JSON 结果: {json_filename}")
        
        # 4. 生成 srt
        if Config.file_save_srt:
            # 构建 words 信息（无需依赖 json 文件）
            words = [{'word': token.replace('@', ''), 'start': timestamp, 'end': timestamp + 0.2} 
                     for (timestamp, token) in zip(timestamps, tokens)]
            for i in range(len(words) - 1):
                words[i]['end'] = min(words[i]['end'], words[i+1]['start'])
            
            text_lines = text_split.splitlines()
            srt_filename = file.with_suffix('.srt')

            srt_from_txt.generate_srt_file(words, text_lines, srt_filename)
        
        # 5. 清理中间生成的 txt
        if not Config.file_save_txt and txt_filename.exists():
            try:
                txt_filename.unlink()
                logger.debug(f"清理中间 TXT 文件: {txt_filename}")
            except Exception as e:
                logger.warning(f"清理中间 TXT 文件失败: {e}")
                
        return text_display
