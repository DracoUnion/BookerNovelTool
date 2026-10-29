#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：主题级联（规则：LDA/频率；LLM：主题推理）。"""

from typing import Optional

from ..util import render_prompt
from .b_topic_network import content_tokens, lda_topics
from .common import Budget
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
)
from .d_pmt import D_TOPIC_PMT
from .llm import MetricsLLM
from .models import TopicResult


def _rule(text: str) -> tuple:
    toks = content_tokens(text)
    if len(toks) < 30:
        return {"topics": [], "topic_overlap": 0}, 0.2, {"method": "too_short"}
    r = lda_topics([toks], num_topics=3, passes=3)
    if not r or "lda_topics" not in r:
        return {"topics": [], "topic_overlap": 0}, 0.2, {"method": "lda_unavailable"}
    conf = min(1.0, len(toks) / 500) * (1 - r.get("topic_overlap", 0))
    return r, conf, {"method": "lda_single"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_TOPIC_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return TopicResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """主题级联。"""
    triggers = any_of(sample(0.05), low_confidence(0.55))
    return run_cascade(
        "topic", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )