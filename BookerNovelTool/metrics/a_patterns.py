#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A 档：句型比例、把/被字句、对话段比、引号/书名号、章节标题模式。"""

import re
from collections import Counter
from typing import List, Optional

from .common import char_count, split_paragraphs, split_sentences

SENT_TYPES = {
    "statement": re.compile(r'[。.]$'),
    "question": re.compile(r'[？?]$'),
    "imperative": re.compile(r'(吧|啊|呀|呢|请|快|别|务必|必须|给我|去|来)[。！!]?$'),
    "exclamation": re.compile(r'[！!]$'),
}


def sentence_type_ratio(sents: List[str]) -> dict:
    """陈述/疑问/祈使/感叹句比例。"""
    if not sents:
        return {}
    c = Counter()
    for s in sents:
        for k, p in SENT_TYPES.items():
            if p.search(s.strip()):
                c[k] += 1
                break
        else:
            c["other"] += 1
    n = len(sents)
    return {k: v / n for k, v in c.items()}


def ba_bei_ratio(text: str) -> dict:
    """把字句/被字句频率（以汉字数为分母）。"""
    n = max(char_count(text), 1)
    return {
        "ba_ratio": len(re.findall(r'把[^，。！？；]{1,10}', text)) / n,
        "bei_ratio": len(re.findall(r'被[^，。！？；]{1,10}', text)) / n,
    }


def dialogue_para_ratio(paras: List[str]) -> float:
    """含引号（对话）段落比例。"""
    if not paras:
        return 0.0
    return sum(1 for p in paras if re.search(r'[“"「『]', p)) / len(paras)


def quote_counts(text: str) -> dict:
    """左右引号数量与书名号数量。"""
    return {
        "quote_left": text.count("“") + text.count("「"),
        "quote_right": text.count("”") + text.count("」"),
        "book_title": len(re.findall(r'《[^》]+》', text)),
    }


def chapter_title_pattern(titles: List[str]) -> dict:
    """章节标题模式占比（第X章/第X节/Chapter N/其他）。"""
    if not titles:
        return {}
    pats = Counter()
    for t in titles:
        if re.match(r'^第[零一二三四五六七八九十百千万\d]+章', t):
            pats["dizhang"] += 1
        elif re.match(r'^第[零一二三四五六七八九十百千万\d]+节', t):
            pats["dijie"] += 1
        elif re.match(r'^Chapter\s+\d+', t, re.I):
            pats["chapter"] += 1
        else:
            pats["other"] += 1
    n = len(titles)
    return {k: v / n for k, v in pats.items()}


def compute(
    text: str,
    titles: Optional[List[str]] = None,
) -> dict:
    """A 档句式与排版模式。"""
    sents = split_sentences(text)
    paras = split_paragraphs(text)
    out = {
        "sentence_type": sentence_type_ratio(sents),
        "ba_bei": ba_bei_ratio(text),
        "dialogue_para_ratio": dialogue_para_ratio(paras),
        "quotes": quote_counts(text),
    }
    if titles:
        out["chapter_title"] = chapter_title_pattern(titles)
    return out