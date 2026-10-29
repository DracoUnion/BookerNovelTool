#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""C 档（必须 LLM）：修辞识别、描写类型、叙事学、风格判断、全书结构。

所有函数都接收 `MetricsLLM` 实例（复用 `BookerNovelTool.openai.OpenAIClient`），
返回对应 Pydantic 模型。
"""

from typing import Optional

from ..util import render_prompt
from .llm import MetricsLLM
from .models import (
    BookResult,
    DescriptionResult,
    NarrativeResult,
    RhetoricResult,
    StyleResult,
)
from .pmt import (
    BOOK_PMT,
    DESCRIPTION_PMT,
    METRICS_SYSTEM,
    NARRATIVE_PMT,
    RHETORIC_PMT,
    STYLE_PMT,
)

DEFAULT_MAX_LEN = 4000  # 单次 LLM 调用截取的文本长度


def _call(metrics_llm: MetricsLLM, pmt: str, model, *, system=METRICS_SYSTEM, **kw):
    """渲染提示词，发起一次结构化 LLM 调用并转换为 Pydantic 模型。"""
    prompt = render_prompt(pmt, **kw)
    data = metrics_llm.llm_json(prompt, system=system)
    return model.model_validate(data)


def analyze_rhetoric(
    metrics_llm: MetricsLLM,
    text: str,
    max_len: int = DEFAULT_MAX_LEN,
) -> RhetoricResult:
    """识别修辞手法。"""
    return _call(metrics_llm, RHETORIC_PMT, RhetoricResult, text=text[:max_len])


def analyze_description(
    metrics_llm: MetricsLLM,
    text: str,
    max_len: int = DEFAULT_MAX_LEN,
) -> DescriptionResult:
    """按句分类描写类型。"""
    return _call(metrics_llm, DESCRIPTION_PMT, DescriptionResult, text=text[:max_len])


def analyze_narrative(
    metrics_llm: MetricsLLM,
    text: str,
    max_len: int = DEFAULT_MAX_LEN,
) -> NarrativeResult:
    """分析叙事学特征。"""
    return _call(metrics_llm, NARRATIVE_PMT, NarrativeResult, text=text[:max_len])


def analyze_style(
    metrics_llm: MetricsLLM,
    text: str,
    max_len: int = DEFAULT_MAX_LEN,
) -> StyleResult:
    """判断文体风格与 AI 味。"""
    return _call(metrics_llm, STYLE_PMT, StyleResult, text=text[:max_len])


def analyze_book(
    metrics_llm: MetricsLLM,
    summaries: str,
    max_len: int = 20000,
) -> BookResult:
    """归纳全书叙事结构（输入各章摘要）。"""
    return _call(
        metrics_llm, BOOK_PMT, BookResult,
        summaries=summaries[:max_len],
    )