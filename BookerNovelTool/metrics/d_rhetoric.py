#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：修辞级联（规则：正则；LLM：完整修辞识别）。"""

import re
from collections import Counter
from typing import Optional

from ..util import render_prompt
from .common import Budget, split_sentences
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
)
from .d_pmt import D_RHETORIC_PMT
from .llm import MetricsLLM
from .models import RhetoricResult

SIMILE = re.compile(r'(像|好像|如同|仿佛|宛如|犹如|似|好似)[^，。！？]{1,20}')
METAPHOR = re.compile(r'([一-鿿]{2,6})(是|成了|变成|化作)([一-鿿]{2,8})')
EXAGGER = re.compile(r'(千|万|亿|极|最|无比|无穷|天崩地裂|惊天动地|排山倒海)')
PERSON_KW = set("哭 笑 怒 叹 唱 舞 沉思 低语 咆哮 挣扎 拥抱 思念 等待 守望".split())
PERSON_TARGET = re.compile(r'(风|雨|月|花|树|山|河|海|石头|城市|灯)')


def _parallel(sents, n=3) -> int:
    hits = 0
    for i in range(len(sents) - n + 1):
        win = sents[i:i + n]
        heads = [s[:2] for s in win]
        lens = [len(s) for s in win]
        if len(set(heads)) == 1 or max(lens) - min(lens) <= 2:
            hits += 1
    return hits


def _rule(text: str) -> tuple:
    sents = split_sentences(text)
    n = max(len(sents), 1)
    simile = len(SIMILE.findall(text))
    metaphor = len(METAPHOR.findall(text))
    exagger = len(EXAGGER.findall(text))
    parallel = _parallel(sents)
    repeat = sum(v - 1 for v in Counter(sents).values() if v > 1)
    person = sum(
        1 for s in sents
        if any(k in s for k in PERSON_KW) and PERSON_TARGET.search(s)
    )
    val = {
        "simile": simile, "metaphor": metaphor, "exaggeration": exagger,
        "parallelism": parallel, "repetition": repeat, "personification": person,
        "rhetoric_density": (simile + metaphor + exagger + parallel + repeat + person) / n,
    }
    conf = 0.7 if (simile + exagger) > 3 else 0.4
    return val, conf, {"method": "regex"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_RHETORIC_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return RhetoricResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """修辞级联。"""
    triggers = any_of(sample(0.05), low_confidence(0.6))
    return run_cascade(
        "rhetoric", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )