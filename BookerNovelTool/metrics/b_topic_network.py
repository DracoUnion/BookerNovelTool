#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：主题与网络（LDA 主题/词共现网络/角色共现网络）。

依赖项皆可选：gensim（LDA）、networkx（网络指标）、hanlp（角色 NER），
缺失时对应部分降级为 available 标记。
"""

import re
from collections import Counter
from typing import Dict, List, Optional

from .common import tokenize

STOP = set(
    "的 了 在 是 我 你 他 她 它 们 这 那 有 和 与 就 都 也 很 不 没 要 会 着 过 "
    "把 被 而 但 或 从 到 对 为 以 于 之 其 中 上 下 里 外 又 还 再 更 最 "
    "一个 没有 什么 自己 知道 时候".split()
)


def content_tokens(text: str) -> List[str]:
    """过滤停用词与单字，只保留中文实词 token。"""
    return [
        w for w in tokenize(text)
        if w not in STOP and len(w) > 1 and re.search(r'[一-鿿]', w)
    ]


def lda_topics(
    chapters_tokens: List[List[str]],
    num_topics: int = 10,
    passes: int = 5,
) -> dict:
    """LDA 主题分布/重叠/连贯性（需 gensim）。"""
    if not chapters_tokens or len(chapters_tokens) < 3:
        return {}
    try:
        from gensim import corpora
        from gensim.models import LdaModel
    except Exception:
        return {"available": False}
    try:
        dictionary = corpora.Dictionary(chapters_tokens)
        dictionary.filter_extremes(no_below=3, no_above=0.5)
        if len(dictionary) < 5:
            return {}
        corpus = [dictionary.doc2bow(t) for t in chapters_tokens]
        lda = LdaModel(
            corpus=corpus, id2word=dictionary,
            num_topics=num_topics, passes=passes, random_state=42,
        )
        twords = [set(w for w, _ in lda.show_topic(i, 10)) for i in range(num_topics)]
        pairs = num_topics * (num_topics - 1) / 2 or 1
        overlap = sum(
            len(twords[i] & twords[j])
            for i in range(num_topics) for j in range(i + 1, num_topics)
        )
        return {
            "lda_topics": [
                [w for w, _ in lda.show_topic(i, 8)] for i in range(num_topics)
            ],
            "topic_overlap": overlap / pairs,
            "n_topics": num_topics,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def _network_metrics(edges: Dict, has_nx: bool) -> dict:
    """由边权字典计算网络指标；有 networkx 时补充聚类系数。"""
    nodes = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    if not nodes:
        return {}
    # 加权度
    deg = Counter()
    for (a, b), w in edges.items():
        deg[a] += w
        deg[b] += w
    out = {
        "nodes": len(nodes),
        "edges": len(edges),
        "avg_degree": sum(deg.values()) / len(deg),
        "top_degree": sorted(deg.items(), key=lambda x: -x[1])[:20],
    }
    if has_nx:
        import networkx as nx

        G = nx.Graph()
        for (a, b), w in edges.items():
            G.add_edge(a, b, weight=w)
        out["clustering"] = nx.average_clustering(G, weight="weight")
    return out


def cooccurrence(text: str, window: int = 5, top_k: int = 300) -> dict:
    """词共现网络（滑动窗口共现）。"""
    try:
        import networkx as nx
        HAS_NX = True
    except Exception:
        HAS_NX = False
    toks = content_tokens(text)
    if len(toks) < 10:
        return {}
    cnt = Counter(toks)
    top = set(w for w, _ in cnt.most_common(top_k))
    edges = {}
    for i, w in enumerate(toks):
        if w not in top:
            continue
        for j in range(i + 1, min(i + window, len(toks))):
            v = toks[j]
            if v in top and v != w:
                key = (w, v) if w < v else (v, w)
                edges[key] = edges.get(key, 0) + 1
    if not edges:
        return {}
    out = _network_metrics(edges, HAS_NX)
    return {f"cooc_{k}" if k != "top_degree" else "cooc_top_degree": v for k, v in out.items()}


def character_network(
    chapters_text: List[str],
    top_k: int = 30,
) -> dict:
    """从章节文本抽取角色共现网络（需 hanlp 与 networkx）。"""
    try:
        from .b_pos_syntax import _load
        nlp = _load()
        import networkx as nx
    except Exception as e:
        return {"error": str(e)}
    try:
        names = Counter()
        for t in chapters_text[:50]:
            doc = nlp(t)
            for e in doc.get("ner/msra") or []:
                if e[1] in ("PERSON", "PER"):
                    names[e[0]] += 1
        top_names = set(n for n, _ in names.most_common(top_k))
        G = nx.Graph()
        for t in chapters_text[:50]:
            doc = nlp(t)
            present = set(
                e[0] for e in doc.get("ner/msra") or []
                if e[1] in ("PERSON", "PER") and e[0] in top_names
            )
            for a in present:
                for b in present:
                    if a < b:
                        G.add_edge(
                            a, b,
                            weight=G.get_edge_data(a, b, {}).get("weight", 0) + 1,
                        )
        if G.number_of_nodes() == 0:
            return {}
        deg = dict(G.degree(weight="weight"))
        return {
            "char_nodes": G.number_of_nodes(),
            "char_edges": G.number_of_edges(),
            "char_top_degree": sorted(deg.items(), key=lambda x: -x[1])[:20],
            "char_clustering": nx.average_clustering(G, weight="weight"),
        }
    except Exception as e:
        return {"error": str(e)}


def compute(
    text: str,
    chapters_tokens: Optional[List[List[str]]] = None,
    chapters_text: Optional[List[str]] = None,
) -> dict:
    """B 档主题与网络指标。"""
    out = {"cooccurrence": cooccurrence(text)}
    if chapters_tokens:
        out.update(lda_topics(chapters_tokens))
    if chapters_text:
        out["character_network"] = character_network(chapters_text)
    return out