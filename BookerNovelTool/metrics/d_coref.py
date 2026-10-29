#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：指代级联（规则：距离启发式；LLM：完整指代消解）。"""

import re
from typing import Optional

from ..util import render_prompt
from .common import Budget, tokenize
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
)
from .d_pmt import D_COREF_PMT
from .llm import MetricsLLM
from .models import CorefResult

PRON = set("他 她 它 他们 她们 它们 这 那 此 该 其 之".split())
NOUN_HINT = re.compile(r'[一-鿿]{2,4}')


def _rule(text: str) -> tuple:
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
    avg = sum(dists) / len(dists) if dists else 0
    val = {
        "pronoun_density": len(pronouns) / n,
        "anaphora_avg_distance": avg,
        "anaphora_max_distance": max(dists) if dists else 0,
        "n_pronoun": len(pronouns),
    }
    conf = 0.3 if avg > 20 else 0.5
    return val, conf, {"method": "distance_heuristic"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_COREF_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return CorefResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """指代级联。"""
    triggers = any_of(sample(0.03), low_confidence(0.6))
    return run_cascade(
        "coref", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )