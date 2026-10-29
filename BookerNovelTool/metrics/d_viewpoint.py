#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：视角级联（规则：人称代词比例；LLM：判断限知/全知等）。"""

from typing import Optional

from ..util import render_prompt
from .b_pos_syntax import compute as pos_compute
from .common import Budget
from .d_cascade import CascadeResult, any_of, always, run_cascade
from .d_pmt import D_VIEWPOINT_PMT
from .llm import MetricsLLM
from .models import ViewpointResult


def _rule(text: str) -> tuple:
    try:
        r = pos_compute(text, max_chars=20000)
    except Exception:
        return {"person": "unknown"}, 0.0, {"method": "pos_unavailable"}
    if not isinstance(r, dict) or r.get("available") is False:
        return {"person": "unknown"}, 0.0, {"method": "pos_unavailable"}
    p1, p2, p3 = r.get("person_1", 0), r.get("person_2", 0), r.get("person_3", 0)
    person = (
        "first" if p1 > max(p2, p3)
        else ("third" if p3 > p2 else "second")
    )
    val = {
        "person": person,
        "person_1": p1,
        "person_2": p2,
        "person_3": p3,
        "viewpoint": "unknown",
    }
    return val, 0.8, {"method": "pronoun_ratio", "need_llm_for_viewpoint": True}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_VIEWPOINT_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return ViewpointResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """视角级联（始终触发 LLM，因为规则无法判断限知/全知）。"""
    triggers = any_of(always)
    return run_cascade(
        "viewpoint", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )