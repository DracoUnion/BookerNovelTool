#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""小说风格/质量评价指标子模块。

指标分四档：
  A 档：纯规则统计（长度/标点/词汇丰富度/信息论/句型/语音）
  B 档：传统 NLP（词法句法/词典类/主题网络/可读性/相似度/衔接连贯）
  C 档：必须 LLM 的语义分析（修辞/描写/叙事学/风格）
  D 档：规则 + LLM 级联（情感/主题/修辞/指代/视角/场景/对话/描写/认知负荷/相似度）

LLM 调用复用 `BookerNovelTool.openai.OpenAIClient`。
"""

from .common import Budget
from .pipeline import (
    compute_ab,
    compute_c,
    compute_d,
    compute_report,
    compute_style_similarity,
)

__all__ = [
    "Budget",
    "compute_ab",
    "compute_c",
    "compute_d",
    "compute_report",
    "compute_style_similarity",
]