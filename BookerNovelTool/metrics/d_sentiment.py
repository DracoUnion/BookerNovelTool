#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：情感级联（规则：词典情感；LLM：复杂情感微调）。"""

from typing import Optional

from ..util import render_prompt
from .b_lexicon import compute as lexicon_compute
from .common import Budget
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
    uncertain,
)
from .d_pmt import D_SENTIMENT_PMT
from .llm import MetricsLLM
from .models import SentimentResult


def _rule(text: str) -> tuple:
    r = lexicon_compute(text)
    emo = r["emotion_word_density"]
    mean = 0.5 + (r["positive_ratio"] - r["negative_ratio"]) * 0.5
    extremity = abs(mean - 0.5) * 2
    conf = min(1.0, emo * 50) * (0.5 + 0.5 * extremity)
    return (
        {
            "sentiment_mean": mean,
            "sentiment_std": 0.0,
            "positive_ratio": r["positive_ratio"],
            "negative_ratio": r["negative_ratio"],
            "emotion_density": emo,
        },
        conf,
        {"method": "lexicon"},
    )


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_SENTIMENT_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return SentimentResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """情感级联。"""
    triggers = any_of(
        sample(0.05), low_confidence(0.5), uncertain(["sentiment_mean"], 0.45, 0.55)
    )
    return run_cascade(
        "sentiment", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )