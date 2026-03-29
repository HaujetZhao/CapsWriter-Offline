#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中文简繁转换模块

基于 MediaWiki 转换表的简繁转换实现。
已修复原 zhconv 库中使用废弃 pkg_resources 的问题。

原库: https://github.com/gumblex/zhconv
许可证: MIT

    >>> print(convert('我幹什麼不干你事。', 'zh-cn'))
    我干什么不干你事。
    >>> print(convert('人体内存在很多微生物', 'zh-tw'))
    人體內存在很多微生物
"""
__version__ = '1.4.3'

import os
import sys
import re
import json
from pathlib import Path

# 修复: 使用 importlib.resources 或直接读取文件，替代废弃的 pkg_resources
def get_module_res(*res):
    """获取模块资源文件"""
    module_dir = Path(__file__).parent
    resource_path = module_dir.joinpath(*res)
    return open(resource_path, 'rb')

# Locale fallback order lookup dictionary
Locales = {
    'zh-cn': ('zh-cn', 'zh-hans', 'zh-sg', 'zh'),
    'zh-hk': ('zh-hk', 'zh-hant', 'zh-tw', 'zh'),
    'zh-tw': ('zh-tw', 'zh-hant', 'zh-hk', 'zh'),
    'zh-sg': ('zh-sg', 'zh-hans', 'zh-cn', 'zh'),
    'zh-my': ('zh-my', 'zh-sg', 'zh-hans', 'zh-cn', 'zh'),
    'zh-mo': ('zh-mo', 'zh-hk', 'zh-hant', 'zh-tw', 'zh'),
    'zh-hant': ('zh-hant', 'zh-tw', 'zh-hk', 'zh'),
    'zh-hans': ('zh-hans', 'zh-cn', 'zh-sg', 'zh'),
    'zh': ('zh',) # special value for no conversion
}

_DEFAULT_DICT = "zhcdict.json"
DICTIONARY = _DEFAULT_DICT

zhcdicts = None
dict_zhcn = None
dict_zhsg = None
dict_zhtw = None
dict_zhhk = None
pfsdict = {}

RE_langconv = re.compile(r'(-\{|\}-)')
RE_splitflag = re.compile(r'\s*\|\s*')
RE_splitmap = re.compile(r'\s*;\s*')
RE_splituni = re.compile(r'\s*=>\s*')
RE_splitpair = re.compile(r'\s*:\s*')

def loaddict(filename=DICTIONARY):
    """
    Load the dictionary from a specific JSON file.
    """
    global zhcdicts
    if zhcdicts:
        return
    if filename == _DEFAULT_DICT:
        zhcdicts = json.loads(get_module_res(filename).read().decode('utf-8'))
    else:
        with open(filename, 'rb') as f:
            zhcdicts = json.loads(f.read().decode('utf-8'))
    zhcdicts['SIMPONLY'] = frozenset(zhcdicts['SIMPONLY'])
    zhcdicts['TRADONLY'] = frozenset(zhcdicts['TRADONLY'])

def getdict(locale):
    """
    Generate or get convertion dict cache for certain locale.
    Dictionaries are loaded on demand.
    """
    global zhcdicts, dict_zhcn, dict_zhsg, dict_zhtw, dict_zhhk, pfsdict
    if zhcdicts is None:
        loaddict(DICTIONARY)
    if locale == 'zh-cn':
        if dict_zhcn:
            got = dict_zhcn
        else:
            dict_zhcn = zhcdicts['zh2Hans'].copy()
            dict_zhcn.update(zhcdicts['zh2CN'])
            got = dict_zhcn
    elif locale == 'zh-tw':
        if dict_zhtw:
            got = dict_zhtw
        else:
            dict_zhtw = zhcdicts['zh2Hant'].copy()
            dict_zhtw.update(zhcdicts['zh2TW'])
            got = dict_zhtw
    elif locale == 'zh-hk' or locale == 'zh-mo':
        if dict_zhhk:
            got = dict_zhhk
        else:
            dict_zhhk = zhcdicts['zh2Hant'].copy()
            dict_zhhk.update(zhcdicts['zh2HK'])
            got = dict_zhhk
    elif locale == 'zh-sg' or locale == 'zh-my':
        if dict_zhsg:
            got = dict_zhsg
        else:
            dict_zhsg = zhcdicts['zh2Hans'].copy()
            dict_zhsg.update(zhcdicts['zh2SG'])
            got = dict_zhsg
    elif locale == 'zh-hans':
        got = zhcdicts['zh2Hans']
    elif locale == 'zh-hant':
        got = zhcdicts['zh2Hant']
    else:
        got = {}
    if locale not in pfsdict:
        pfsdict[locale] = getpfset(got)
    return got

def getpfset(convdict):
    pfset = []
    for word in convdict:
        for ch in range(len(word)):
            pfset.append(word[:ch+1])
    return frozenset(pfset)

def issimp(s, full=False):
    """
    Detect text is whether Simplified Chinese or Traditional Chinese.
    Returns True for Simplified; False for Traditional; None for unknown.
    If full=False, it returns once first simplified- or traditional-only
    character is encountered, so it's for quick and rough identification;
    else, it compares the count and returns the most likely one.
    Use `is` (True/False/None) to check the result.

    `s` must be unicode (Python 2) or str (Python 3), or you'll get None.
    """
    if zhcdicts is None:
        loaddict(DICTIONARY)
    simp, trad = 0, 0
    if full:
        for ch in s:
            if ch in zhcdicts['SIMPONLY']:
                simp += 1
            elif ch in zhcdicts['TRADONLY']:
                trad += 1
        if simp > trad:
            return True
        elif simp < trad:
            return False
        else:
            return None
    else:
        for ch in s:
            if ch in zhcdicts['SIMPONLY']:
                return True
            elif ch in zhcdicts['TRADONLY']:
                return False
        return None

def fallback(locale, mapping):
    for l in Locales[locale]:
        if l in mapping:
            return mapping[l]
    return convert(tuple(mapping.values())[0], locale)

def convtable2dict(convtable, locale, update=None):
    """
    Convert a list of conversion dict to a dict for a certain locale.

    >>> sorted(convtable2dict([{'zh-hk': '列斯', 'zh-hans': '利兹', 'zh': '利兹', 'zh-tw': '里茲'}, {':uni': '巨集', 'zh-cn': '宏'}], 'zh-cn').items())
    [('列斯', '利兹'), ('利兹', '利兹'), ('巨集', '宏'), ('里茲', '利兹')]
    """
    rdict = update.copy() if update else {}
    for r in convtable:
        if ':uni' in r:
            if locale in r:
                rdict[r[':uni']] = r[locale]
        elif locale[:-1] == 'zh-han':
            if locale in r:
                for word in r.values():
                    rdict[word] = r[locale]
        else:
            v = fallback(locale, r)
            for word in r.values():
                rdict[word] = v
    return rdict

def tokenize(s, locale, update=None):
    """
    Tokenize `s` according to corresponding locale dictionary.
    Don't use this for serious text processing.
    """
    zhdict = getdict(locale)
    pfset = pfsdict[locale]
    if update:
        zhdict = zhdict.copy()
        zhdict.update(update)
        newset = set()
        for word in update:
            for ch in range(len(word)):
                newset.add(word[:ch+1])
        pfset = pfset | newset
    ch = []
    N = len(s)
    pos = 0
    while pos < N:
        i = pos
        frag = s[pos]
        maxword = None
        maxpos = 0
        while i < N and frag in pfset:
            if frag in zhdict:
                maxword = frag
                maxpos = i
            i += 1
            frag = s[pos:i+1]
        if maxword is None:
            maxword = s[pos]
            pos += 1
        else:
            pos = maxpos + 1
        ch.append(maxword)
    return ch

def convert(s, locale, update=None):
    """
    Main convert function.

    :param s: must be `unicode` (Python 2) or `str` (Python 3).
    :param locale: should be one of ``('zh-hans', 'zh-hant', 'zh-cn', 'zh-sg'
                               'zh-tw', 'zh-hk', 'zh-my', 'zh-mo')``.
    :param update: a dict which updates the conversion table, eg.
        ``{'from1': 'to1', 'from2': 'to2'}``

    >>> print(convert('我幹什麼不干你事。', 'zh-cn'))
    我干什么不干你事。
    >>> print(convert('我幹什麼不干你事。', 'zh-cn', {'不干': '不幹'}))
    我干什么不幹你事。
    >>> print(convert('人体内存在很多微生物', 'zh-tw'))
    人體內存在很多微生物
    """
    if locale == 'zh' or locale not in Locales:
        # "no conversion"
        return s
    zhdict = getdict(locale)
    pfset = pfsdict[locale]
    newset = set()
    if update:
        # TODO: some sort of caching
        #zhdict = zhdict.copy()
        #zhdict.update(update)
        newset = set()
        for word in update:
            for ch in range(len(word)):
                newset.add(word[:ch+1])
        #pfset = pfset | newset
    ch = []
    N = len(s)
    pos = 0
    while pos < N:
        i = pos
        frag = s[pos]
        maxword = None
        maxpos = 0
        while i < N and (frag in pfset or frag in newset):
            if update and frag in update:
                maxword = update[frag]
                maxpos = i
            elif frag in zhdict:
                maxword = zhdict[frag]
                maxpos = i
            i += 1
            frag = s[pos:i+1]
        if maxword is None:
            maxword = s[pos]
            pos += 1
        else:
            pos = maxpos + 1
        ch.append(maxword)
    return ''.join(ch)

def convert_for_mw(s, locale, update=None):
    """
    Recognizes MediaWiki's human conversion format.
    Use locale='zh' for no conversion.

    Reference: (all tests passed)
    https://zh.wikipedia.org/wiki/Help:高级字词转换语法
    https://www.mediawiki.org/wiki/Writing_systems/Syntax
    """
    ch = []
    rules = []
    ruledict = update.copy() if update else {}
    nested = 0
    block = ''
    for frag in RE_langconv.split(s):
        if frag == '-{':
            nested += 1
            block += frag
        elif frag == '}-':
            if not nested:
                # bogus }-
                ch.append(frag)
                continue
            block += frag
            nested -= 1
            if nested:
                continue
            newrules = []
            delim = RE_splitflag.split(block[2:-2].strip(' \t\n\r\f\v;'))
            if len(delim) == 1:
                flag = None
                mapping = RE_splitmap.split(delim[0])
            else:
                flag = RE_splitmap.split(delim[0].strip(' \t\n\r\f\v;'))
                mapping = RE_splitmap.split(delim[1])
            rule = {}
            for m in mapping:
                uni = RE_splituni.split(m)
                if len(uni) == 1:
                    pair = RE_splitpair.split(uni[0])
                else:
                    if rule:
                        newrules.append(rule)
                        rule = {':uni': uni[0]}
                    else:
                        rule[':uni'] = uni[0]
                    pair = RE_splitpair.split(uni[1])
                if len(pair) == 1:
                    rule['zh'] = convert_for_mw(pair[0], 'zh', ruledict)
                else:
                    rule[pair[0]] = convert_for_mw(pair[1], pair[0], ruledict)
            newrules.append(rule)
            if not flag:
                ch.append(fallback(locale, newrules[0]))
            elif any(ch in flag for ch in 'ATRD-HN'):
                for f in flag:
                    # A: add rule for convert code (all text convert)
                    # H: Insert a conversion rule without output
                    if f in ('A', 'H'):
                        for r in newrules:
                            if not r in rules:
                                rules.append(r)
                        if f == 'A':
                            if ':uni' in r:
                                if locale in r:
                                    ch.append(r[locale])
                                else:
                                    ch.append(convert(r[':uni'], locale))
                            else:
                                ch.append(fallback(locale, newrules[0]))
                    # -: remove convert
                    elif f == '-':
                        for r in newrules:
                            try:
                                rules.remove(r)
                            except ValueError:
                                pass
                    # D: convert description (useless)
                    #elif f == 'D':
                        #ch.append('; '.join(': '.join(x) for x in newrules[0].items()))
                    # T: title convert (useless)
                    # R: raw content (implied above)
                    # N: current variant name (useless)
                    #elif f == 'N':
                        #ch.append(locale)
                ruledict = convtable2dict(rules, locale, update)
            else:
                fblimit = frozenset(flag) & frozenset(Locales[locale])
                limitedruledict = update.copy() if update else {}
                for r in rules:
                    if ':uni' in r:
                        if locale in r:
                            limitedruledict[r[':uni']] = r[locale]
                    else:
                        v = None
                        for l in Locales[locale]:
                            if l in r and l in fblimit:
                                v = r[l]
                                break
                        for word in r.values():
                            limitedruledict[word] = v if v else convert(word, locale)
                ch.append(convert(delim[1], locale, limitedruledict))
            block = ''
        elif nested:
            block += frag
        else:
            ch.append(convert(frag, locale, ruledict))
    if nested:
        # unbalanced
        ch.append(convert_for_mw(block + '}-'*nested, locale, ruledict))
    return ''.join(ch)


if __name__ == '__main__':
    # 简单测试
    print("简体 -> 繁体（标准）:")
    print(convert('人体内存在很多微生物', 'zh-hant'))
    print("\n简体 -> 繁体（台湾）:")
    print(convert('人体内存在很多微生物', 'zh-tw'))
    print("\n繁体 -> 简体:")
    print(convert('我幹什麼不干你事。', 'zh-cn'))
