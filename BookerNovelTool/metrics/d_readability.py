#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：认知负荷级联（规则：公式可读性；LLM：解释难点与读者层级）。"""

from typing import Optional

from ..util import render_prompt
from .b_readability import compute as readability_compute
from .common import Budget
from .d_cascade import (
    CascadeResult,
    anomaly,
    any_of,
    run_cascade,
    sample,
)
from .d_pmt import D_READABILITY_PMT
from .llm import MetricsLLM
from .models import CognitiveLoadResult


def _rule(text: str) -> tuple:
    r = readability_compute(text)
    score = r.get("readability_score", 0)
    return r, 0.55, {"method": "formula"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_READABILITY_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return CognitiveLoadResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """认知负荷级联。"""
    triggers = any_of(sample(0.05), anomaly(2.0, ["readability_score"]))
    return run_cascade(
        "readability", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )