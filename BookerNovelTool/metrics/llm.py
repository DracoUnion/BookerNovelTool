#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LLM 包装：复用 `BookerNovelTool.openai.OpenAIClient`，带磁盘缓存。

- `MetricsLLM`：持有 OpenAIClient 实例 + 缓存目录。
- `MetricLLMCache`：共享进程内缓存，避免同一片段重复调用。

用法：
    从项目 XML 风格约定看，本项目 LLM 调用统一走 `openai.OpenAIClient`。
    这里只做薄封装，把缓存和重试集中起来。
"""

import hashlib
import json
import os
import re
from os import path
from typing import Any, Callable, Dict, List, Optional

from ..util import read_text, write_text
from ..openai import OpenAIClient


class MetricsLLM:
    """基于 OpenAIClient 的指标 LLM 调用器，带磁盘与进程内缓存。"""

    def __init__(self, llm: OpenAIClient, model: str, cache_dir: str = ".metrics_cache"):
        self.llm = llm
        self.model = model
        self.cache_dir = cache_dir
        self._process_cache: Dict[str, Any] = {}

    @classmethod
    def from_args(cls, args, cache_dir: str = ".metrics_cache"):
        """从命令行参数构造（对应项目其他模块的 from_args 约定）。"""
        llm = OpenAIClient.from_args(args)
        model = getattr(args, 'model', 'gpt-4o-mini')
        return cls(llm, model, cache_dir)

    def _cache_path(self, key: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        return path.join(self.cache_dir, key[:2], key + ".json")

    def llm_json(
        self,
        prompt: str,
        system: str = "你只输出 JSON，不解释，不新增原文没有的信息。",
        max_tokens: Optional[int] = 4096,
        temp: float = 0.1,
    ) -> dict:
        """调用一次 LLM 并解析 JSON 输出（带缓存）。"""
        key = hashlib.md5((system + prompt).encode('utf-8')).hexdigest()
        if key in self._process_cache:
            return self._process_cache[key]
        fname = self._cache_path(key)
        if fname and path.isfile(fname):
            raw = read_text(fname)
            if raw:
                try:
                    data = json.loads(raw)
                    self._process_cache[key] = data
                    return data
                except json.JSONDecodeError:
                    pass

        def _parse(raw: str) -> dict:
            text = raw.strip()
            text = re.sub(r'^```(?:json)?|```$', '', text).strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]+\}', text)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except json.JSONDecodeError:
                        pass
                raise ValueError('LLM 输出未包含合法 JSON')

        result = self.llm.call_llm_retry(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            self.model,
            retry=3,
            temp=temp,
            max_tokens=max_tokens,
            parse_output=_parse,
        )
        self._process_cache[key] = result
        if fname:
            write_text(fname, json.dumps(result, ensure_ascii=False))
        return result

    def llm_valid_json(self, prompt: str, **kw) -> Optional[dict]:
        """调用 llm_json，但要求结果不含 parse_failed 错误标记。"""
        try:
            data = self.llm_json(prompt, **kw)
        except Exception:
            return None
        if isinstance(data, dict) and "error" in data and "raw" in data:
            return None
        return data