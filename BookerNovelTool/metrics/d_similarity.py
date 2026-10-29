#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：风格相似度增强（规则相似度 + 可选中文 embedding）。"""

from typing import Optional

import numpy as np

from .b_similarity import burrows_delta, cosine_sim, kl_js
from .common import Budget

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    return _embedder


def _embedding(a: str, b: str) -> Optional[dict]:
    try:
        emb = _get_embedder().encode([a, b], normalize_embeddings=True)
        return {"embedding_cosine": float(np.dot(emb[0], emb[1])), "method": "bge-small-zh"}
    except Exception:
        return None


def compute(a: str, b: str, budget: Budget, force_embedding: bool = False) -> dict:
    """规则相似度；边界不确定或强制时尝试 embedding 增强。"""
    ra, rb = a[:2000], b[:2000]
    rule = {
        "cosine": cosine_sim(ra, rb),
        "kl_js": kl_js(ra, rb),
        "burrows_delta": burrows_delta(ra, rb),
    }
    need = force_embedding or 0.4 <= rule["cosine"] <= 0.7
    embedding = None
    if need and budget.can_call():
        budget.consume()
        embedding = _embedding(a[:3000], b[:3000])
    return {
        "rule": rule,
        "embedding": embedding,
        "source": "fused" if embedding else "rule",
    }