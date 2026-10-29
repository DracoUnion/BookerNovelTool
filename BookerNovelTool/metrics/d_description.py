#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：描写类型级联（规则：关键词；LLM：按句分类）。"""

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
from .d_pmt import D_DESCRIPTION_PMT
from .llm import MetricsLLM
from .models import DescriptionResult

DESC_KW = {
    "psych": set("想 觉得 感到 心中 心里 思绪 念头 回忆 意识到 明白 希望 害怕 担心 犹豫".split()),
    "action": set("跑 走 冲 抓 挥 打 踢 跳 转身 推 拉 拿 放 坐 站 起 落".split()),
    "environment": set("天 云 风 雨 雪 山 河 树 花 草 街 屋 房 灯 光 影 声音 气味 空气 阳光 月色".split()),
    "dialogue": set("说 道 问 答 喊 叫 低语 笑道 冷笑 叹气".split()),
}


def _rule(text: str) -> tuple:
    sents = split_sentences(text)
    n = max(len(sents), 1)
    counts = {k: 0 for k in DESC_KW}
    for s in sents:
        for k, kws in DESC_KW.items():
            if any(w in s for w in kws):
                counts[k] += 1
                break
    ratios = {k: v / n for k, v in counts.items()}
    return {"counts": counts, "ratios": ratios, "n_sent": n}, 0.5, {"method": "keyword_dict"}


def _llm(metrics_llm: MetricsLLM, text: str) -> dict:
    prompt = render_prompt(D_DESCRIPTION_PMT, text=text[:4000])
    data = metrics_llm.llm_json(prompt)
    return DescriptionResult.model_validate(data).model_dump()


def compute(
    metrics_llm: Optional[MetricsLLM],
    text: str,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """描写类型级联。"""
    triggers = any_of(sample(0.05), low_confidence(0.6))
    return run_cascade(
        "description", text, _rule,
        (lambda t: _llm(metrics_llm, t)) if metrics_llm else None,
        [triggers], budget, ctx,
    )