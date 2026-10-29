#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""metrics 子模块的智能体：统一持有 LLM 客户端，复用项目 OpenAIClient。"""

from .c_semantic import (
    analyze_book, analyze_description, analyze_narrative,
    analyze_rhetoric, analyze_style,
)
from .llm import MetricsLLM


class MetricsAgent:
    """封装 C/D 档所有大模型调用。"""

    def __init__(self, args, cache_dir=None):
        self.args = args
        self.max_chars = getattr(args, 'max_chars', 4000)
        self.llm = MetricsLLM.from_args(
            args, cache_dir or getattr(args, 'asset_dir', '.metrics_cache')
        )

    def analyze_rhetoric(self, text):
        return analyze_rhetoric(self.llm, text, self.max_chars)

    def analyze_description(self, text):
        return analyze_description(self.llm, text, self.max_chars)

    def analyze_narrative(self, text):
        return analyze_narrative(self.llm, text, self.max_chars)

    def analyze_style(self, text):
        return analyze_style(self.llm, text, self.max_chars)

    def analyze_book(self, summaries):
        return analyze_book(self.llm, summaries)

    @property
    def available(self):
        return self.llm is not None
