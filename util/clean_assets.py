__doc__ = """
This script is used to clean all assets not referenced by Markdown files.
本脚本的作用是，递归清理所有未被 Markdown 引用的图片、音频附件
"""

import re
import sys
from os import remove
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token
from rich.console import Console

if __name__ != "__main__":
    raise ImportError(f"Script {__file__} should not be imported as a module")

console = Console(highlight=False, soft_wrap=False)

markdown_ext = ["md", "markdown"]
asset_ext = ["jpg", "jpeg", "png", "wav", "mp3", "mp4"]


def get_md_files(
    path: str | Path,
) -> list[Path]:  # 从输入目录递归搜索所有的 Markdown 文件
    p = Path(path)
    if not p.exists():
        return []
    if not p.is_dir():
        return []

    md_files = list[Path]()
    for ext in markdown_ext:
        md_files.extend(list(p.glob("**/*." + ext)))

    return md_files


def get_links(text: str) -> list[str]:  # 查找文本内的所有链接
    links = list[str]()

    def add_link(token: Token):
        if "src" in token.attrs:
            src = token.attrs["src"]
            assert isinstance(
                src, str
            ), f"src should be str, but got {type(src)}"
            links.append(unquote(src))
        if "href" in token.attrs:
            href = token.attrs["href"]
            assert isinstance(
                href, str
            ), f"href should be str, but got {type(href)}"
            links.append(unquote(href))
        if token.type == "html_inline":
            m = re.match(r'.*src="(.+?)".*', token.content)
            if m:
                links.append(unquote(m.group(1)))
        elif token.type == "text":
            for m in re.finditer(r".*?\[\[(.+?)\]\]", token.content):
                links.append(unquote(m.group(1)))
        if token.children is None:
            return
        for t in token.children:
            add_link(t)

    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    for t in md.parse(text):
        add_link(t)

    return links


def get_absolute_local_paths(
    source_file_path: str | Path, links: list[str]
) -> list[Path]:
    # 验证链接是本地文件
    source_file_path = Path(source_file_path)
    links_paths = list[Path]()

    for link in links:
        if (source_file_path.parent / link).exists():
            links_paths.append(source_file_path.parent / link)
            continue

        p = Path(link)
        if p.exists():
            links_paths.append(p)
            continue
        console.print(f"[red]文件 {source_file_path} 中的链接 {link} 不存在")

    return links_paths


def main() -> None:
    # 默认清理当前所在文件夹
    root = Path(__file__).parent

    # 若参数提供了其他文件夹，则清理提供的文件夹
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists() and p.is_dir():
            root = p
    console.print(f"[yellow]{__doc__}\n")
    console.print(f"[green]当前所要清理的根目录是：{root}\n")
    console.input("[green]确认请按回车，接下来将搜索 Markdown 文件\n")

    # 收集到所有的 Markdown 文件
    md_files = get_md_files(root)
    console.print("[green]共找到了如下 Markdown 文件：")
    for f in md_files:
        console.print(f"    {f}")
    console.line()
    console.input("[green]确认请按回车，接下来将搜索未被引用的附件\n")

    # 收集到所有被引用的附件
    links_used = list[Path]()
    for md in md_files:
        with open(md, "r", encoding="utf-8") as f:
            text = f.read()
        links = get_links(text)
        link_paths = get_absolute_local_paths(md, links)
        links_used.extend(link_paths)

    # 收集所有的附件文件夹
    folders = set(link.parent for link in links_used)

    # 收集所有附件文件夹中的附件
    links_all = list[Path]()
    for folder in folders:
        if not folder.is_relative_to(root):
            continue
        for ext in asset_ext:
            links_all.extend(list(folder.glob("**/*." + ext)))
    links_all = list(set(links_all))

    # 得到没有被使用的附件
    links_unused = set(links_all) - set(links_used)
    console.print("[yellow]共查找到以下没有被引用的附件：")
    for file in sorted(links_unused):
        console.print(f"    {file}")
    for _ in range(3):
        if (
            console.input(
                "[yellow]如果确认删除，请手动输入单词 delete 后回车\n"
            )
            == "delete"
        ):
            break
    else:
        console.print("[red]三次未输入 delete，判断为不删除，退出")
        sys.exit()

    # 执行删除
    console.print("[red]开始删除")
    for f in links_unused:
        remove(f)
        console.print(f"    [red]{f}")
    console.input("[green]清理完成，按回车退出")


if __name__ == "__main__":
    main()
