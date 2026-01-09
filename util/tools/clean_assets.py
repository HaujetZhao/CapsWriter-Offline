from importlib.util import find_spec
relies = ['markdown_it', 'rich']
if not all([find_spec(x) for x in relies]):
    print('这个脚本需要用到第三方库：markdown_it rich\n请先用 pip 安装后再运行')
    input('按回车退出')

import re
import os
import sys
from os import remove
from pathlib import Path
from typing import List
from pprint import pprint
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token
from rich.console import Console

console = Console(highlight=0, soft_wrap=False)

markdown_ext = ['md', 'markdown']
asset_ext = ['jpg', 'jpeg', 'png', 'wav', 'mp3', 'mp4']



def get_md_files(path):         # 从输入目录递归搜索所有的 Markdown 文件
    p = Path(path)
    if not p.exists(): return []
    if not p.is_dir(): return []

    md_files = []
    for ext in markdown_ext:
        md_files.extend(list(p.glob("**/*." + ext)))

    return md_files


def get_links(text: str):       # 查找文本内的所有链接
    links = []

    def add_link(token: Token):
        if 'src' in token.attrs:
            links.append(unquote(token.attrs['src']))
        if 'href' in token.attrs:
            links.append(unquote(token.attrs['href']))
        if token.type == 'html_inline':
            m = re.match(r'.*src="(.+?)".*', token.content)
            if m: links.append(unquote(m.group(1)))
        elif token.type == 'text':
            for m in re.finditer(r'.*?\[\[(.+?)\]\]', token.content):
                links.append(unquote(m.group(1)))
        if token.children is None: return
        for t in token.children:
            add_link(t)

    md = (MarkdownIt('commonmark' ,{'breaks':True,'html':True}))
    # pprint(md.parse(text))
    for t in md.parse(text):
        add_link(t)

    return links


def absolutify_links(file, links: List[str]):   # 验证链接是本地文件
    if type(file) is not Path: file = Path(file)
    
    temp_links = links.copy(); links.clear()
    for link in temp_links:
        if (file.parent / link).exists():
            links.append(file.parent / link)
            continue
        elif Path(link).exists():
            links.append(link)


def main():
    # 默认清理当前所在文件夹
    root = Path(__file__).parent

    # 若参数提供了其他文件夹，则清理提供的文件夹
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists() and p.is_dir(): root = p
    console.print(f'[yellow]本脚本的作用是，递归清理所有未被 Markdown 引用的图片、音频附件\n')
    console.print(f'[green]当前所要清理的根目录是：{root}\n')
    console.input(f'[green]确认请按回车，接下来将搜索 Markdown 文件\n')

    # 收集到所有的 Markdown 文件
    md_files = get_md_files(root)
    console.print(f'[green]共找到了如下 Markdown 文件：')
    for f in md_files:console.print(f'    {f}')
    console.line()
    console.input(f'[green]确认请按回车，接下来将搜索未被引用的附件\n')

    # 收集到所有被引用的附件
    links_used = []
    for md in md_files:
        with open(md, "r", encoding="utf-8") as f: text = f.read()
        links = get_links(text)
        absolutify_links(md, links)
        links_used.extend(links)

    # 收集所有的附件文件夹
    folders = set(l.parent for l in links_used)

    # 收集所有附件文件夹中的附件
    links_all = []
    for folder in folders:
        if not folder.is_relative_to(root): continue
        for markdown_ext in asset_ext:
            links_all.extend(list(folder.glob("**/*." + markdown_ext)))
    links_all = list(set(links_all))
    
    # 得到没有被使用的附件
    links_unused = set(links_all) - set(links_used)
    console.print('[yellow]共查找到以下没有被引用的附件：')
    for file in sorted(links_unused):
        console.print(f'    {file}')
    for i in range(3):
        if console.input(f'[yellow]如果确认删除，请手动输入单词 delete 后回车\n') == 'delete': break
    else:
        console.print('[red]三次未输入 delete，判断为不删除，退出')
        sys.exit()
    
    # 执行删除
    console.print('[red]开始删除')
    for f in links_unused:
        remove(f); console.print(f'    [red]{f}')
    console.input(f'[green]清理完成，按回车退出')


if __name__ == "__main__":
    main()