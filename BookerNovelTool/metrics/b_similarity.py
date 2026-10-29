#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：风格相似度（余弦/KL/JS/Burrows Delta/Zeta），纯 numpy 实现。"""

from collections import Counter

import numpy as np

from .common import tokenize


def _char_counter(text: str) -> Counter:
    return Counter(c for c in text if c.strip())


def cosine_sim(a: str, b: str) -> float:
    """字符级词袋余弦相似度。"""
    ca, cb = _char_counter(a), _char_counter(b)
    vocab = set(ca) | set(cb)
    va = np.array([ca.get(c, 0) for c in vocab], dtype=float)
    vb = np.array([cb.get(c, 0) for c in vocab], dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(va @ vb / denom) if denom else 0.0


def _freq(text: str, top: int = 500) -> dict:
    toks = tokenize(text)
    c = Counter(toks)
    total = sum(c.values()) or 1
    return {w: v / total for w, v in c.most_common(top)}


def kl_js(a: str, b: str, top: int = 500) -> dict:
    """KL 散度与 JS 散度（基于词频分布）。"""
    fa, fb = _freq(a, top), _freq(b, top)
    vocab = list(set(fa) | set(fb))
    eps = 1e-9
    pa = np.array([fa.get(w, eps) for w in vocab])
    pb = np.array([fb.get(w, eps) for w in vocab])
    pa /= pa.sum()
    pb /= pb.sum()
    kl_ab = float((pa * np.log(pa / pb)).sum())
    m = (pa + pb) / 2
    js = float(0.5 * (pa * np.log(pa / m)).sum() + 0.5 * (pb * np.log(pb / m)).sum())
    return {"kl_ab": kl_ab, "js": js}


def burrows_delta(a: str, b: str, top: int = 200) -> float:
    """Burrows's Delta 差异度（越小越相似）。"""
    fa, fb = _freq(a, top), _freq(b, top)
    vocab = list(set(fa) | set(fb))
    va = np.array([fa.get(w, 0) for w in vocab])
    vb = np.array([fb.get(w, 0) for w in vocab])
    mu = (va + vb) / 2
    sd = np.sqrt(((va - mu) ** 2 + (vb - mu) ** 2) / 2) + 1e-9
    return float(np.abs((va - mu) / sd - (vb - mu) / sd).mean())


def zeta(a: str, b: str, top: int = 200) -> float:
    """Zeta：a 特有高频词相对于并集的比例。"""
    sa = set(w for w, _ in Counter(tokenize(a)).most_common(top))
    sb = set(w for w, _ in Counter(tokenize(b)).most_common(top))
    if not (sa | sb):
        return 0.0
    return len(sa - sb) / len(sa | sb)


def compute(a: str, b: str) -> dict:
    """B 档风格相似度指标。"""
    return {
        "cosine": cosine_sim(a, b),
        "kl_js": kl_js(a, b),
        "burrows_delta": burrows_delta(a, b),
        "zeta": zeta(a, b),
    }