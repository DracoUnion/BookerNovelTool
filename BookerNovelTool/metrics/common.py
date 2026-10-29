#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""公共工具：分词、分句、基础统计、LLM 预算。

需要 numpy 与 jieba；其余重型依赖（hanlp/gensim/networkx/pypinyin 等）
在各模块内部按需导入，缺失时相应指标优雅降级。
"""

import re
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

import jieba
import numpy as np

CJK = re.compile(r'[一-鿿]')
SENT_END = re.compile(r'([。！？!?…]+[”’"』」]?)')
CLAUSE_SPLIT = re.compile(r'[，,；;：:]')


def split_paragraphs(text: str) -> List[str]:
    """按空行或换行切分段落。"""
    return [p.strip() for p in re.split(r'\n\s*\n|\n', text) if p.strip()]


def split_sentences(text: str) -> List[str]:
    """按句末标点切分句子（保留引号括号等收尾符）。"""
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    parts, sents, buf = SENT_END.split(text), [], ""
    for p in parts:
        if not p:
            continue
        buf += p
        if SENT_END.fullmatch(p):
            sents.append(buf.strip())
            buf = ""
    if buf.strip():
        sents.append(buf.strip())
    return [s for s in sents if s]


def split_clauses(sent: str) -> List[str]:
    """按逗号/分号/冒号把句子切分为小句（分句）。"""
    return [c for c in CLAUSE_SPLIT.split(sent) if c.strip()]


def tokenize(text: str) -> List[str]:
    """结巴分词，去除空白 token。"""
    return [t for t in jieba.lcut(text) if t.strip()]


def char_count(s: str) -> int:
    """汉字数（不含标点/字母/数字）。"""
    return len(CJK.findall(s))


def word_count(s: str) -> int:
    """词数。"""
    return len(tokenize(s))


def entropy(counter: Counter) -> float:
    """Counter 的信息熵（以 2 为底）。"""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    ps = np.array([v / total for v in counter.values()])
    return float(-(ps * np.log2(ps)).sum())


def compression_ratio(text: str) -> float:
    """gzip 压缩率（越小越冗余、越可预测）。"""
    raw = text.encode('utf-8')
    return len(zlib.compress(raw, 9)) / max(len(raw), 1)


def hist(values, bucket_size: int) -> Dict[int, int]:
    """按桶宽聚合直方图 {桶起点: 计数}。"""
    return {
        int(k): v for k, v in Counter(
            (v // bucket_size) * bucket_size for v in values
        ).items()
    }


def desc(arr) -> Dict[str, float]:
    """分布描述统计：均值/中位数/标准差/方差/变异系数/偏度/峰度。"""
    a = np.asarray(arr, dtype=float)
    if a.size == 0:
        return {}
    out = {
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "std": float(a.std(ddof=1)) if a.size > 1 else 0.0,
        "var": float(a.var(ddof=1)) if a.size > 1 else 0.0,
    }
    out["cv"] = out["std"] / out["mean"] if out["mean"] else 0.0
    if a.size > 1 and out["std"] > 0:
        z = (a - a.mean()) / (a.std(ddof=0) or 1e-9)
        out["skew"] = float((z ** 3).mean())
        out["kurtosis"] = float((z ** 4).mean() - 3)
    return out


@dataclass
class Budget:
    """LLM 调用预算：达到上限后不再发起新的 LLM 调用。"""

    max_calls: int = 10_000
    calls: int = 0

    def can_call(self) -> bool:
        return self.calls < self.max_calls

    def consume(self):
        self.calls += 1

    def reset(self):
        self.calls = 0