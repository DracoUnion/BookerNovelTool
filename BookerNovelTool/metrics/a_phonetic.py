#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A 档（可选）：声调分布、押韵密度、生僻字比例、拼音长度。

依赖 pypinyin；未安装时相关指标降级并标记 available=False。
"""

from collections import Counter
from typing import List, Optional

from .common import CJK, split_sentences

try:
    from pypinyin import lazy_pinyin, Style
    HAS_PINYIN = True
except Exception:
    HAS_PINYIN = False

# 简易常用字表（可替换为通用规范汉字表）
COMMON = set(
    "的一是不了人我在有他这为之大来以个中上们到说国和地也子时道出而要于就"
    "下得可你年生自会那后能对着事其里所去行过家十用发天如然作方成者多日都"
    "三小军二无同么经法当起与好看学进种将还分此心前面又定见只主没公从"
)


def rare_char_ratio(text: str) -> float:
    """生僻字比例（不在常用字表中的汉字占比）。"""
    chars = [c for c in text if CJK.match(c)]
    if not chars:
        return 0.0
    return sum(1 for c in chars if c not in COMMON) / len(chars)


def pinyin_lazy(chars: str) -> List[str]:
    """带声调编号的拼音列表（lazy_pinyin(Style.TONE3) 或空）。"""
    if not HAS_PINYIN:
        return []
    try:
        return lazy_pinyin(chars, style=Style.TONE3)
    except Exception:
        return []


def phonetic_stats(text: str) -> dict:
    """声调分布、押韵密度、平均拼音长度。"""
    if not HAS_PINYIN:
        return {"available": False}
    chars = [c for c in text if CJK.match(c)]
    if not chars:
        return {"available": False}
    tones = [t for t in pinyin_lazy("".join(chars)) if t]
    if not tones:
        return {"available": False}
    n = len(tones)
    tone_cnt = Counter(t[-1] if t[-1].isdigit() else "0" for t in tones)
    # 押韵：相邻句尾字韵母相同比例
    sents = split_sentences(text)
    ends = []
    for s in sents:
        last = s[-1]
        if CJK.match(last):
            fs = lazy_pinyin(last, style=Style.FINALS)
            if fs:
                ends.append(fs[0])
    rhyme = sum(1 for i in range(len(ends) - 1) if ends[i] == ends[i + 1])
    return {
        "available": True,
        "tone_dist": {k: v / n for k, v in tone_cnt.items()},
        "avg_pinyin_len": sum(len(t) for t in tones) / n,
        "rhyme_adjacent_ratio": rhyme / max(len(ends) - 1, 1),
    }


def compute(text: str) -> dict:
    """A 档语音指标。"""
    return {
        "phonetic": phonetic_stats(text),
        "rare_char_ratio": rare_char_ratio(text),
    }