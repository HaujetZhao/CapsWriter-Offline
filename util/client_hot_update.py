from os import getcwd, sep, path
import time
from util.client_cosmic import console
from util import hot_sub_zh
from util import hot_sub_en
from util import hot_sub_rule
from util import hot_kwds
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


path_zh = Path() / "hot-zh.txt"
path_en = Path() / "hot-en.txt"
path_rule = Path() / "hot-rule.txt"
path_kwds = Path() / "keywords.txt"


def update_hot_zh():
    if not path_zh.exists():
        with open(path_zh, "w", encoding="utf-8") as f:
            f.write('# 在此文件放置中文热词，每行一个，开头带井号表示注释，会被省略')
    with open(path_zh, "r", encoding="utf-8") as f:
        num_hot_zh = hot_sub_zh.更新热词词典(f.read())
    console.print(f'已载入 [green4]{num_hot_zh:5}[/] 条中文热词')


def update_hot_en():
    if not path_en.exists():
        with open(path_en, "w", encoding='utf-8') as f:
            f.write(
                '# 在此文件放置英文热词 \n# Put English hot words here, one per line. Line starts with # will be ignored. ')
    with open(path_en, "r", encoding="utf-8") as f:
        num_hot_en = hot_sub_en.更新热词词典(f.read())
    console.print(f'已载入 [green4]{num_hot_en:5}[/] 条英文热词')


def update_hot_rule():
    if not path_rule.exists():
        with open(path_rule, "w", encoding='utf-8') as f:
            f.write(
r'''# 在此文件放置自定义规则，每行一条正则表达式，
# 左边是查找模式，右边是替换式，中间用带空格的等号分开
# 以 # 开头的会被忽略，将查找和匹配用等号隔开，文本两边的空格会被省略。例如：

毫安时     =      mAh
赫兹      =      Hz
伏特      =        V
二、      =        二
负一      =    -1
(艾特)\s*(QQ)\s*点\s*            =     @qq.
(艾特)\s*([一幺]六三)\s*点\s*     =     @163.
(艾特)\s*(\w+)\s*(点)\s*(\w+)    =     @\2.\4
''')
    with open(path_rule, "r", encoding="utf-8") as f:
        num_hot_rule = hot_sub_rule.更新热词词典(f.read())
    console.print(f'已载入 [green4]{num_hot_rule:5}[/] 条自定义替换规则')


def update_hot_kwds():
    if not path_kwds.exists():
        with open(path_kwds, "w", encoding='utf-8') as f:
            f.write(
                '# 在此文件放置日记关键词，每行一个，开头带井号表示注释，会被省略\n# 当识别结果以关键词开头时，会被记录到 「年份/月份/关键词-日期.md」文件中\n重要\n健康\n学习')
    with open(path_kwds, "r", encoding="utf-8") as f:
        num_kwd = hot_kwds.do_updata_kwd(f.read())
    console.print(f'已载入 [green4]{num_kwd:5}[/] 条日记关键词')


def update_hot_all():
    update_hot_zh()
    update_hot_en()
    update_hot_rule()
    update_hot_kwds()
    console.line()


def observe_hot():
    observer = Observer()
    observer.schedule(HotHandler(), '.', recursive=False)
    observer.start()
    return observer

class HotHandler(FileSystemEventHandler):
    """用于动态更新热词的处理器"""

    last_time = 0

    updates = {
        path_zh: update_hot_zh,
        path_en: update_hot_en,
        path_rule: update_hot_rule,
        path_kwds: update_hot_kwds,
    }

    def on_modified(self, event):
        # 事件间隔小于2秒就取消
        if time.time() - self.last_time < 2:
            return

        # 路径不对就取消
        event_path = Path(event.src_path)
        if event_path not in self.updates:
            return

        # 更新时间
        self.last_time = time.time()

        # 延迟0.2秒，避免编辑器还没有将热词文件更新完成导致读空
        time.sleep(0.2)
        console.print('[green4]检测到配置文件更新，[/]', end='')

        # 更新
        try:
            self.updates[event_path]()
            console.line()
        except Exception as e:
            console.print(f'更新热词失败：{e}', style='bright_red')
