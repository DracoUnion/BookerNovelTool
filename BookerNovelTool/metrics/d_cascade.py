#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档：规则 + LLM 级联框架。

每个指标定义一个规则函数（返回 (值, 置信度, 元信息)），
只有当触发条件（低置信度/不确定区间/异常值/抽样等）满足时才调用 LLM，
LLM 结果与规则结果融合后返回。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .common import Budget

# 规则函数签名：fn(text) -> (value, confidence, meta)
RuleFn = Callable[[str], tuple]
# LLM 函数签名：fn(text) -> Any
LlmFn = Callable[[str], Any]
# 触发条件签名：fn(value, ctx) -> (触发与否, 原因)
Trigger = Callable[[Any, dict], tuple]


@dataclass
class CascadeResult:
    """级联计算结果。"""

    value: Any
    source: str = "rule"          # rule / llm / fused
    confidence: float = 1.0
    rule_value: Any = None
    llm_value: Any = None
    agreement: Optional[float] = None
    reason: str = ""
    meta: dict = field(default_factory=dict)


# ──── 触发条件构建器 ────


def always(_r=None, _ctx=None) -> tuple:
    return True, "always"


def never(_r=None, _ctx=None) -> tuple:
    return False, ""


def sample(ratio: float = 0.05, seed: int = 42) -> Trigger:
    """按固定比例抽样。"""
    import random
    rnd = random.Random(seed)

    def fn(r, ctx):
        return (rnd.random() < ratio, "sample")
    return fn


def low_confidence(th: float = 0.6) -> Trigger:
    """规则置信度低于阈值。"""
    def fn(r, ctx):
        conf = ctx.get("confidence", 1.0)
        return (conf < th, f"conf<{th}")
    return fn


def uncertain(keys: List[str], lo: float = 0.35, hi: float = 0.65) -> Trigger:
    """值落在不确定区间（如情感均值接近中性）。"""
    def fn(r, ctx):
        for k in keys:
            v = r.get(k) if isinstance(r, dict) else None
            if isinstance(v, (int, float)) and lo <= v <= hi:
                return (True, f"{k} gray")
        return (False, "")
    return fn


def anomaly(z_th: float = 2.0, keys: Optional[List[str]] = None) -> Trigger:
    """偏离全局统计均值超过 z 倍标准差。"""
    def fn(r, ctx):
        stats = ctx.get("global_stats", {})
        for k in keys or []:
            v = r.get(k) if isinstance(r, dict) else None
            s = stats.get(k)
            if v is None or not s or s.get("std", 0) == 0:
                continue
            if abs(v - s["mean"]) / s["std"] > z_th:
                return (True, f"{k} z>{z_th}")
        return (False, "")
    return fn


def critical(pred: Callable[[dict], bool]) -> Trigger:
    """根据上下文自定义条件。"""
    def fn(r, ctx):
        return (pred(ctx), "critical")
    return fn


def any_of(*triggers: Trigger) -> Trigger:
    """任一触发条件满足即触发。"""
    def fn(r, ctx):
        for t in triggers:
            ok, why = t(r, ctx)
            if ok:
                return (True, why)
        return (False, "")
    return fn


# ──── 融合 ────


def _agree(a, b) -> Optional[float]:
    """规则值与 LLM 值的对齐度 0-1。"""
    if a is None or b is None:
        return None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return max(0.0, 1 - abs(a - b) / max(abs(a), abs(b), 1e-9))
    if isinstance(a, dict) and isinstance(b, dict):
        keys = set(a) & set(b)
        if not keys:
            return None
        return sum(1 for k in keys if a[k] == b[k]) / len(keys)
    return 1.0 if a == b else 0.0


def fuse(rv, lv, prefer: str = "llm"):
    """规则值与 LLM 值融合，返回 (值, 来源, 对齐度)。"""
    if lv is None:
        return rv, "rule", None
    if rv is None:
        return lv, "llm", None
    if prefer == "llm":
        return lv, "fused", _agree(rv, lv)
    return rv, "fused", _agree(rv, lv)


# ──── 级联主流程 ────


def run_cascade(
    name: str,
    text: str,
    rule_fn: RuleFn,
    llm_fn: LlmFn,
    triggers: list,
    budget: Budget,
    ctx: Optional[dict] = None,
) -> CascadeResult:
    """先跑规则，触发条件满足且预算充足时调用 LLM，融合后返回。"""
    ctx = dict(ctx or {})
    rv, conf, meta = rule_fn(text)
    ctx = {**ctx, "confidence": conf, "name": name}

    need, why = False, ""
    for t in triggers:
        ok, reason = t(rv, ctx)
        if ok:
            need, why = True, reason
            break

    if need and llm_fn and budget.can_call():
        budget.consume()
        try:
            lv = llm_fn(text)
        except Exception as e:
            return CascadeResult(
                rv, "rule", conf, rv, None,
                reason=f"{why}; err={e}", meta=meta,
            )
        val, src, agree = fuse(rv, lv)
        return CascadeResult(val, src, conf, rv, lv, agree, why, meta)

    return CascadeResult(
        rv, "rule", conf, rv, None, reason=why or "no_trigger", meta=meta,
    )