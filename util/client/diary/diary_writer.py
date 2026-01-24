# coding: utf-8
"""
日记写入模块

提供 DiaryWriter 类用于将识别结果写入 Markdown 日记文件。
"""

from __future__ import annotations

import time
from os import makedirs
from pathlib import Path
from typing import Optional, List

from util.client.state import console
from . import logger


# MD 文件头部模板
HEADER_MD = r'''```txt
正则表达式 Tip

匹配到音频文件链接：\[(.+)\]\((.{10,})\)[\s]*
替换为 HTML 控件：<audio controls><source src="$2" type="audio/mpeg">$1</audio>\n\n

匹配 HTML 控件：<audio controls><source src="(.+)" type="audio/mpeg">(.+)</audio>\n\n
替换为文件链接：[$2]($1) 
```


'''


class DiaryWriter:
    """
    日记写入器
    
    负责将识别结果写入 Markdown 日记文件：
    - 根据日期创建文件夹结构
    - 链接音频文件
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        初始化日记写入器
        
        Args:
            base_path: 基础路径，默认为当前目录
        """
        self.base_path = base_path or Path()
    
    def write(
        self,
        text: str,
        time_start: float,
        file_audio: Optional[Path] = None
    ) -> List[Path]:
        """
        写入日记
        
        Args:
            text: 识别文本
            time_start: 录音开始时间戳
            file_audio: 音频文件路径（可选）
            
        Returns:
            写入的日记文件路径列表
        """
        local_time = time.localtime(time_start)
        time_year = time.strftime('%Y', local_time)
        time_month = time.strftime('%m', local_time)
        time_day = time.strftime('%d', local_time)
        time_hms = time.strftime('%H:%M:%S', local_time)
        
        folder_path = self.base_path / time_year / time_month
        makedirs(folder_path, exist_ok=True)
        
        # 按日期归档
        file_md = folder_path / f'{time_day}.md'
        
        # 确保 md 文件存在
        if not file_md.exists():
            self._create_md(file_md)
        
        # 构建日记条目
        if file_audio:
            try:
                path_rel = file_audio.relative_to(file_md.parent).as_posix()
                path_rel = path_rel.replace(" ", "%20")
            except ValueError:
                path_rel = file_audio.as_posix().replace(" ", "%20")
        else:
            path_rel = ""
        
        # 写入 md
        with open(file_md, 'a', encoding='utf-8') as f:
            if path_rel:
                f.write(f'[{time_hms}]({path_rel}) {text}\n\n')
            else:
                f.write(f'{time_hms} {text}\n\n')
        
        logger.debug(f"写入日记: {file_md.name}")
        return [file_md]
        
        return written_files
    
    def _create_md(self, file_md: Path) -> None:
        """创建新的 MD 文件"""
        with open(file_md, 'w', encoding='utf-8') as f:
            f.write(HEADER_MD)
        logger.debug(f"创建日记文件: {file_md}")
