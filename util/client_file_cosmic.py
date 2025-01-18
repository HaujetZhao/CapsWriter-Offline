from rich.console import Console
from rich.theme import Theme

my_theme = Theme({"markdown.code": "cyan", "markdown.item.number": "yellow"})
console = Console(highlight=False, soft_wrap=False, theme=my_theme)


# pylint: disable=too-few-public-methods
class Cosmic:
    """
    用一个 class 存储需要跨模块访问的变量值，命名为 Cosmic
    """

    # not implemented
    # pylint: disable=unnecessary-pass
