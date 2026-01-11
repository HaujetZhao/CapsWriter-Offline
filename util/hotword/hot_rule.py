# coding: utf-8
"""
规则纠错器 (Rule Corrector)

基于正则表达式的精确规则替换。
适用于固定格式的替换（单位、符号、格式等）。

使用方法示例：
```python
corrector = RuleCorrector()
corrector.update_rules('''
    毫安时  =  mAh
    伏特   =   V
    赫兹   =   Hz
    (艾特)\\s*(\\w+)\\s*(点)\\s*(\\w+)    =    @$2.$4
''')

corrector.correct('这款手机有5000毫安时的大电池')  # 输出：这款手机有5000mAh的大电池
corrector.correct('国内交流电一般是50赫兹')       # 输出：国内交流电一般是50Hz
```
"""

import re
from threading import Lock
from typing import Dict


class RuleCorrector:
    """规则纠错器 - 基于规则表达式的精确替换"""

    def __init__(self):
        self.patterns: Dict[str, str] = {}
        self._lock = Lock()

    def update_rules(self, rule_text: str) -> int:
        """
        更新规则词典（线程安全）

        Args:
            rule_text: 规则文本，每行一条，格式为 "正则模式 = 替换文本"

        Returns:
            加载的规则数量
        """
        new_patterns = {}

        for line in rule_text.splitlines():
            if not line or line.startswith('#'):
                continue

            parts = line.split(' = ')
            if len(parts) == 2:
                pattern = parts[0].strip()
                replacement = parts[1].strip()
                new_patterns[pattern] = replacement

        with self._lock:
            self.patterns = new_patterns

        return len(new_patterns)

    def substitute(self, text: str) -> str:
        """
        执行规则替换

        Args:
            text: 原始文本

        Returns:
            替换后的文本
        """
        if not text or not self.patterns:
            return text

        result = text

        with self._lock:
            patterns = self.patterns.copy()

        for pattern, replacement in patterns.items():
            try:
                result = re.sub(pattern, replacement, result)
            except Exception:
                # 忽略无效的正则表达式
                pass

        return result


if __name__ == '__main__':
    print('-------------规则纠错器测试---------------')

    rules = '''
        毫安时  =  mAh
        伏特   =   V
        赫兹   =   Hz
        (艾特)\\s*(\\w+)\\s*(点)\\s*(\\w+)    =    @$2.$4
    '''

    # 新接口
    corrector = CorrectorRule()
    corrector.update_rules(rules)

    print("\n=== 新接口测试 ===")
    print(f"输入: '这款手机有5000毫安时的大电池'")
    print(f"输出: {corrector.correct('这款手机有5000毫安时的大电池')}")

    print(f"\n输入: '国内交流电一般是50赫兹'")
    print(f"输出: {corrector.correct('国内交流电一般是50赫兹')}")

    # 旧接口（向后兼容）
    print("\n=== 旧接口测试（向后兼容）===")
    更新热词词典(rules)

    res = 热词替换('这款手机有5000毫安时的大电池')
    print(f"输入: '这款手机有5000毫安时的大电池'")
    print(f"输出: {res}")

    res2 = 热词替换('国内交流电一般是50赫兹')
    print(f"输入: '国内交流电一般是50赫兹'")
    print(f"输出: {res2}")
