#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A 档：词汇丰富度（TTR 家族）、信息论（熵/压缩率）、n-gram 重复与多样性。"""

import math
from collections import Counter

import numpy as np

from .common import char_count, compression_ratio, entropy, tokenize

WINDOW = 100  # MSTTR 滑动窗口大小


def _ttr(tokens) -> float:
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def lexical_richness(tokens) -> dict:
    """词汇丰富度：TTR/MSTTR/RTTR/Log TTR/Maas/Yule/Simpson/Herdan/Brunet/Honoré/Zipf。"""
    n = len(tokens)
    if n == 0:
        return {}
    types = len(set(tokens))
    freq = Counter(tokens)
    windows = [tokens[i:i + WINDOW] for i in range(0, n - WINDOW + 1, WINDOW)]
    msttr = (
        float(np.mean([_ttr(w) for w in windows])) if n >= WINDOW else _ttr(tokens)
    )
    hapax = sum(1 for v in freq.values() if v == 1) / n
    dis = sum(1 for v in freq.values() if v == 2) / n
    top1k = sum(v for _, v in freq.most_common(1000)) / n
    m2 = sum(v * v for v in freq.values())
    yule_k = 1e4 * (m2 - n) / (n * n) if n else 0.0
    simpson = (
        sum(v * (v - 1) for v in freq.values()) / (n * (n - 1)) if n > 1 else 0.0
    )
    herdan = math.log(types) / math.log(n) if n > 1 else 0.0
    brunet = n ** (types ** -0.165) if types > 0 else 0.0
    honore = (
        100 * math.log(n) / max(1 - hapax * n / max(types, 1), 1e-9)
        if types else 0.0
    )
    # Zipf 斜率：对 log(词频排序名次) ~ log(出现次数) 拟合
    ranks = np.arange(1, len(freq) + 1)
    fs = np.array(sorted(freq.values(), reverse=True), dtype=float)
    zipf = (
        float(np.polyfit(np.log(ranks), np.log(fs), 1)[0]) if len(fs) > 2 else 0.0
    )
    return {
        "n_token": n,
        "n_type": types,
        "ttr": types / n,
        "rttr": types / math.sqrt(n),
        "log_ttr": herdan,
        "msttr": msttr,
        "maas": (
            (math.log(n) - math.log(types)) / (math.log(n) ** 2)
            if n > 1 and types else 0.0
        ),
        "yule_k": yule_k,
        "simpson_d": simpson,
        "herdan_c": herdan,
        "brunet_w": brunet,
        "honore_r": honore,
        "hapax_ratio": hapax,
        "dis_ratio": dis,
        "top1k_coverage": top1k,
        "zipf_slope": zipf,
    }


def info_metrics(text: str, tokens) -> dict:
    """字符/词熵与压缩率。"""
    return {
        "char_entropy": entropy(Counter(text)),
        "word_entropy": entropy(Counter(tokens)),
        "compression_ratio": compression_ratio(text),
    }


def ngram_repeat(tokens, n: int = 4) -> float:
    """重复 n-gram 占比（出现次数 >1 的 n-gram 覆盖比例）。"""
    if len(tokens) < n:
        return 0.0
    grams = [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
    c = Counter(grams)
    return sum(v for v in c.values() if v > 1) / len(grams)


def ngram_diversity(tokens, n: int = 3) -> float:
    """n-gram 多样性（不重复 n-gram 占比）。"""
    if len(tokens) < n:
        return 0.0
    grams = [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
    return len(set(grams)) / len(grams)


def compute(text: str) -> dict:
    """A 档词汇与信息论指标。"""
    toks = tokenize(text)
    return {
        "lexical": lexical_richness(toks),
        "info": info_metrics(text, toks),
        "ngram3_diversity": ngram_diversity(toks, 3),
        "ngram4_repeat": ngram_repeat(toks, 4),
    }