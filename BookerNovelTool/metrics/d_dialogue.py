#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：对话/叙述比级联（规则：引号特征；LLM：识别自由间接引语等）。"""

import re
from typing import Optional

from ..util import render_prompt
from .common import Budget, char_count
from .d_cascade import (
    CascadeResult,
    any_of,
    low_confidence,
    run_cascade,
    sample,
)
from .d_pmt import D_DIALOGUE_PMT
from .llm import MetricsLLM
from .models import DialogueResult

QUOTE = re.compile(r'[“"「『]([^”"」』]{1,500})[”"」』]')


def _rule(text: str) -> tuple:
    quotes = QUOTE.findall(text)
    dchars = sum(char_count(q) for q in quotes)
    total = max(char_count(text), 1)
    val = {
        "dialogue_char_ratio": dchars / total,
        "n_quote_segments": len(quotes),
        "avg_quote_len": dchars / max(len(quotes), 1),
    }
    conf = 0.7 if len(quotes) > 3 else 0.4
    return val, conf, {"method": "quote_regex"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_DIALOGUE_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return DialogueResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """对话/叙述比级联。"""
    triggers = any_of(sample(0.05), low_confidence(0.6))
    return run_cascade(
        "dialogue", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )