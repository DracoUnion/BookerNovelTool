#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""四档指标聚合管线。"""

from typing import Dict, Iterable, List, Optional, Set

from . import (
    a_lexical, a_patterns, a_phonetic, a_punctuation, a_text_stats,
    b_cohesion, b_lexicon, b_pos_syntax, b_readability, b_similarity,
    b_topic_network,
)
from .common import Budget, tokenize
from . import (
    d_coref, d_description, d_dialogue, d_readability, d_rhetoric,
    d_scene, d_sentiment, d_similarity, d_topic, d_viewpoint,
)


def _model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _model_dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_model_dump(v) for v in value]
    return value


def _cascade_dump(result):
    return _model_dump({
        "value": result.value,
        "source": result.source,
        "confidence": result.confidence,
        "rule_value": result.rule_value,
        "llm_value": result.llm_value,
        "agreement": result.agreement,
        "reason": result.reason,
        "meta": result.meta,
    })


def compute_ab(
    text: str,
    chapters_text: Optional[List[str]] = None,
    titles: Optional[List[str]] = None,
    *,
    use_pos: bool = True,
    use_lexicon: bool = True,
    use_topic: bool = False,
    use_cohesion: bool = False,
    use_phonetic: bool = False,
    max_nlp_chars: Optional[int] = None,
) -> dict:
    """计算 A+B 档指标；重型 B 指标按开关启用。"""
    out = {
        "a_text": a_text_stats.compute(text, chapters_text),
        "a_punct": a_punctuation.compute(text),
        "a_lexical": a_lexical.compute(text),
        "a_patterns": a_patterns.compute(text, titles),
        "b_readability": b_readability.compute(text),
    }
    if use_phonetic:
        out["a_phonetic"] = a_phonetic.compute(text)
    if use_pos:
        out["b_pos_syntax"] = b_pos_syntax.compute(text, max_nlp_chars)
    if use_lexicon:
        out["b_lexicon"] = b_lexicon.compute(text)
    if use_topic:
        chapters_tokens = [
            b_topic_network.content_tokens(chapter)
            for chapter in (chapters_text or [])
        ]
        out["b_topic_network"] = b_topic_network.compute(
            text, chapters_tokens or None, chapters_text
        )
    if use_cohesion:
        out["b_cohesion"] = b_cohesion.compute(text, use_entity=use_pos)
    return out


def compute_c(
    agent,
    text: str,
    budget: Budget,
    enable: Optional[Set[str]] = None,
) -> dict:
    """计算 C 档 LLM 语义指标。"""
    enable = enable or {"rhetoric", "description", "narrative", "style"}
    out = {}
    calls = {
        "rhetoric": agent.analyze_rhetoric,
        "description": agent.analyze_description,
        "narrative": agent.analyze_narrative,
        "style": agent.analyze_style,
    }
    for name in enable:
        if name not in calls or not budget.can_call():
            continue
        budget.consume()
        try:
            out[name] = _model_dump(calls[name](text))
        except Exception as error:
            out[name] = {"error": str(error)}
    return out


def compute_d(
    text: str,
    budget: Budget,
    metrics_llm=None,
    ctx: Optional[dict] = None,
    enable: Optional[Set[str]] = None,
) -> dict:
    """计算 D 档规则 + LLM 级联指标。"""
    enable = enable or {
        "sentiment", "topic", "rhetoric", "coref", "viewpoint",
        "scene", "dialogue", "description", "readability",
    }
    fns = {
        "sentiment": d_sentiment.compute,
        "topic": d_topic.compute,
        "rhetoric": d_rhetoric.compute,
        "coref": d_coref.compute,
        "viewpoint": d_viewpoint.compute,
        "scene": d_scene.compute,
        "dialogue": d_dialogue.compute,
        "description": d_description.compute,
        "readability": d_readability.compute,
    }
    out = {}
    for name, fn in fns.items():
        if name not in enable:
            continue
        try:
            out[name] = _cascade_dump(fn(metrics_llm, text, budget, ctx))
        except Exception as error:
            out[name] = {"error": str(error)}
    return out


def compute_style_similarity(
    a: str,
    b: str,
    budget: Optional[Budget] = None,
    force_embedding: bool = False,
) -> dict:
    """计算 B 档规则相似度及 D 档可选 embedding 增强。"""
    budget = budget or Budget(max_calls=0)
    return d_similarity.compute(a, b, budget, force_embedding)


def compute_report(
    text: str,
    *,
    agent=None,
    chapters_text: Optional[List[str]] = None,
    titles: Optional[List[str]] = None,
    tier: str = "all",
    budget: Optional[Budget] = None,
    baseline: Optional[str] = None,
    use_pos: bool = True,
    use_lexicon: bool = True,
    use_topic: bool = False,
    use_cohesion: bool = False,
    use_phonetic: bool = False,
    max_nlp_chars: Optional[int] = None,
) -> dict:
    """按档位生成完整评价报告。"""
    budget = budget or Budget()
    report = {}
    if tier in ("ab", "all"):
        report["ab"] = compute_ab(
            text, chapters_text, titles,
            use_pos=use_pos, use_lexicon=use_lexicon,
            use_topic=use_topic, use_cohesion=use_cohesion,
            use_phonetic=use_phonetic, max_nlp_chars=max_nlp_chars,
        )
    if tier in ("c", "all"):
        report["c"] = compute_c(agent, text, budget) if agent else {}
    if tier in ("d", "all"):
        report["d"] = compute_d(
            text, budget, agent.llm if agent else None,
        )
    if baseline is not None:
        report["similarity"] = compute_style_similarity(text, baseline, budget)
    report["budget"] = {"max_calls": budget.max_calls, "calls": budget.calls}
    return report
