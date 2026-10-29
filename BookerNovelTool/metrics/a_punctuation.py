#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A 档：标点频率/密度/多样性/熵、未配对引号、排版统计。"""

from collections import Counter
from typing import List

import numpy as np

from .common import char_count, split_paragraphs

PUNCTS = list("，。！？；：、,.!?;:…—-\"'“”‘’()（）《》【】[]")
OPEN_PAIRS = {"“": "”", "（": "）", "《": "》", "【": "】", "「": "」", "『": "』"}


def punct_stats(text: str) -> dict:
    """标点总频率、密度、各标点频次分布、熵、多样性、未配对引号。"""
    cnt = Counter(c for c in text if c in PUNCTS)
    total = sum(cnt.values()) or 1
    freq = {p: cnt.get(p, 0) / total for p in PUNCTS}
    probs = np.array([v for v in freq.values() if v > 0])
    ent = float(-(probs * np.log2(probs)).sum()) if probs.size else 0.0
    unpaired = 0
    for open_ch, close_ch in OPEN_PAIRS.items():
        unpaired += abs(text.count(open_ch) - text.count(close_ch))
    return {
        "punct_total": int(total),
        "punct_density": total / max(char_count(text), 1),
        "punct_freq": freq,
        "punct_entropy": ent,
        "punct_diversity": len(cnt) / len(PUNCTS),
        "unpaired_quote": int(unpaired),
    }


def layout_stats(text: str, paras: List[str]) -> dict:
    """空行密度、段首缩进比例、段均行数。"""
    return {
        "blank_line_density": text.count("\n\n") / max(len(paras), 1),
        "indent_para_ratio": sum(
            1 for p in paras if p.startswith(("　", " ", "\t"))
        ) / max(len(paras), 1),
        "avg_para_line": (
            float(np.mean([len(p.split("\n")) for p in paras])) if paras else 0
        ),
    }


def compute(text: str) -> dict:
    """A 档标点与排版统计。"""
    paras = split_paragraphs(text)
    return {"punct": punct_stats(text), "layout": layout_stats(text, paras)}