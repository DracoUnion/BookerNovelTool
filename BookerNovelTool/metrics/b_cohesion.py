#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：衔接与连贯（指代密度/回指距离/衔接词/词汇链/实体网格）。"""

import re
from collections import Counter
from typing import Optional

from .common import split_sentences, tokenize

PRON = set("他 她 它 他们 她们 它们 这 那 此 该 其 之".split())
CONNECT = set(
    "因为 所以 但是 然而 而且 并且 虽然 尽管 如果 那么 因此 于是 接着 然后 "
    "最后 首先 其次 总之 例如 比如 此外 同时".split()
)
NOUN_HINT = re.compile(r'[一-鿿]{2,4}')


def pronoun_anaphora(text: str) -> dict:
    """代词密度与回指距离（向前 30 词内最近的名词线索）。"""
    toks = tokenize(text)
    pronouns = [(i, t) for i, t in enumerate(toks) if t in PRON]
    n = max(len(toks), 1)
    dists = []
    for idx, _ in pronouns:
        for j in range(idx - 1, max(idx - 30, -1), -1):
            w = toks[j]
            if w in PRON or len(w) < 2:
                continue
            if NOUN_HINT.fullmatch(w):
                dists.append(idx - j)
                break
    return {
        "pronoun_density": len(pronouns) / n,
        "anaphora_avg_distance": sum(dists) / len(dists) if dists else 0,
        "anaphora_max_distance": max(dists) if dists else 0,
        "n_pronoun": len(pronouns),
    }


def connective_density(text: str) -> dict:
    """衔接词密度与多样性。"""
    toks = tokenize(text)
    n = len(toks) or 1
    c = Counter(toks)
    return {
        "connective_density": sum(c[w] for w in CONNECT if w in c) / n,
        "connective_diversity": len([w for w in CONNECT if w in c]),
    }


def lexical_chain(text: str, top_k: int = 20) -> dict:
    """用高频内容词近似词汇链。"""
    toks = [t for t in tokenize(text) if len(t) > 1]
    c = Counter(toks)
    chain = c.most_common(top_k)
    return {
        "chain_top": chain,
        "chain_diversity": len(set(w for w, _ in chain)) / max(top_k, 1),
    }


def entity_grid(text: str) -> dict:
    """简化实体网格：句级实体连续性（需 hanlp）。"""
    try:
        from .b_pos_syntax import _load
        nlp = _load()
    except Exception as e:
        return {"error": str(e)}
    try:
        sents = split_sentences(text)
        grids = []
        for s in sents[:100]:
            doc = nlp(s)
            ents = set(
                e[0] for e in doc.get("ner/msra") or []
                if e[1] in ("PERSON", "PER", "LOC", "ORG")
            )
            grids.append(ents)
        continuity = sum(
            1 for i in range(len(grids) - 1) if grids[i] & grids[i + 1]
        ) / max(len(grids) - 1, 1)
        return {"entity_continuity": continuity, "n_sent": len(sents)}
    except Exception as e:
        return {"error": str(e)}


def compute(text: str, use_entity: bool = False) -> dict:
    """B 档衔接连贯指标。"""
    out = {
        "pronoun_anaphora": pronoun_anaphora(text),
        "connective": connective_density(text),
        "lexical_chain": lexical_chain(text),
    }
    if use_entity:
        out["entity_grid"] = entity_grid(text)
    return out