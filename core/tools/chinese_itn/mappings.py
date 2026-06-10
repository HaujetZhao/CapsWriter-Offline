# coding: utf-8
"""
配置和映射表 (数据解耦重构版)
"""

from pathlib import Path
import json
import re

# 定位静态资源 JSON 文件路径
_current_dir = Path(__file__).resolve().parent
_units_path = _current_dir / 'resources' / 'units.json'
_idioms_path = _current_dir / 'resources' / 'idioms.json'

# 动态加载物理单位映射
try:
    with open(_units_path, 'r', encoding='utf-8') as _f:
        unit_mapping = json.load(_f)
except Exception:
    # 防御性回滚兜底
    unit_mapping = {}

# 动态加载成语黑名单
try:
    with open(_idioms_path, 'r', encoding='utf-8') as _f:
        idioms = json.load(_f)
except Exception:
    idioms = []

# 生成单位正则（按长度从长到短排序，确保先匹配长的）
_sorted_units = sorted(unit_mapping.keys(), key=len, reverse=True)
common_units = '|'.join(f'{re.escape(u)}' for u in _sorted_units)

# 中文数字映射表
num_mapper = {
    '零': '0',  '一': '1',  '幺': '1',  '二': '2',
    '两': '2',  '三': '3',  '四': '4',  '五': '5',
    '六': '6',  '七': '7',  '八': '8',  '九': '9',
    '点': '.',
}

# 中文数字对数值的映射
value_mapper = {
    '零': 0,  '一': 1,  '幺': 1,  '二': 2,  '两': 2,  '三': 3,  '四': 4,  '五': 5,
    '六': 6,  '七': 7,  '八': 8,  '九': 9,  "十": 10,  "百": 100,
    "千": 1000,  "万": 10000,  "亿": 100000000,
}

# 模糊表达黑名单（包含"几"的表达不转换）
fuzzy_regex = re.compile(r'几')
