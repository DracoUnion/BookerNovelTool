#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：可读性公式、阅读时间预测、LIX、生僻字。"""

import math

from .a_phonetic import rare_char_ratio
from .common import char_count, split_sentences, word_count


def compute(text: str) -> dict:
    """可读性得分 0-100、阅读时间、年级水平、LIX。"""
    sents = split_sentences(text)
    if not sents:
        return {}
    chars, words = char_count(text), word_count(text)
    asl = words / len(sents)          # 平均句长（词）
    asw = chars / words if words else 0  # 平均词长（字）
    rare = rare_char_ratio(text)
    score = max(0.0, min(100.0, 100 - 1.5 * asl - 20 * asw - 40 * rare))
    return {
        "avg_sent_len_word": asl,
        "avg_word_len_char": asw,
        "rare_char_ratio": rare,
        "readability_score": score,
        "grade_level": max(1, round((100 - score) / 10)),
        "reading_time_min": chars / 400,  # 中文约 400 字/分钟
        "lix": asl + 100 * rare,
    }