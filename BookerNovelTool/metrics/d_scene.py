#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：场景级联（规则：时间/地点标记；LLM：段落级场景切分）。"""

import re
from typing import Optional

from ..util import render_prompt
from .common import Budget, split_paragraphs
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
)
from .d_pmt import D_SCENE_PMT
from .llm import MetricsLLM
from .models import SceneResult

TIME_SHIFT = re.compile(
    r'(第二天|次日|翌日|几天后|数日后|与此同时|同一时间|片刻后|许久|傍晚|清晨|夜晚|深夜|黎明)'
)
PLACE_SHIFT = re.compile(r'(来到|走进|回到|离开|抵达|身处|站在|坐在)[^，。！？]{2,15}')


def _rule(text: str) -> tuple:
    paras = split_paragraphs(text)
    n = len(paras)
    if n == 0:
        return {"n_scenes": 0, "scene_sizes": [], "boundaries": []}, 0.35, {"method": "marker_regex"}
    bounds = [0]
    for i, p in enumerate(paras):
        if i == 0:
            continue
        if TIME_SHIFT.search(p) or PLACE_SHIFT.search(p):
            bounds.append(i)
    bounds.append(n)
    return (
        {
            "n_scenes": len(bounds) - 1,
            "scene_sizes": [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)],
            "boundaries": bounds[:-1],
        },
        (0.6 if len(bounds) - 1 > 1 else 0.35),
        {"method": "marker_regex"},
    )


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    paras = split_paragraphs(text)
    numbered = "\n".join(f"[{i}] {p[:200]}" for i, p in enumerate(paras))
    prompt = render_prompt(D_SCENE_PMT, text=numbered[:5000])
    data = metrics_llm.llm_json(prompt)
    return SceneResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """场景切分级联。"""
    triggers = any_of(sample(0.05), low_confidence(0.65))
    return run_cascade(
        "scene", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )