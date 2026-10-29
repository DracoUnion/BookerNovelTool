#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A 档：字数/词数/句段章长度与分布、分句小句。"""

from typing import List, Optional

from .common import (
    char_count,
    desc,
    hist,
    split_clauses,
    split_paragraphs,
    split_sentences,
    word_count,
)


def sentence_stats(sents: List[str]) -> dict:
    """句子长度与分布、分句/小句统计。"""
    if not sents:
        return {}
    clen = [char_count(s) for s in sents]
    wlen = [word_count(s) for s in sents]
    clauses = [c for s in sents for c in split_clauses(s)]
    return {
        "n_sent": len(sents),
        "sent_char": desc(clen),
        "sent_word": desc(wlen),
        "sent_char_hist": hist(clen, 5),
        "avg_clause_per_sent": len(clauses) / len(sents),
        "clause_char": desc([char_count(c) for c in clauses]),
        "clause_word": desc([word_count(c) for c in clauses]),
    }


def paragraph_stats(paras: List[str]) -> dict:
    """段落长度与分布、单句段/长段比例。"""
    if not paras:
        return {}
    plen = [char_count(p) for p in paras]
    psent = [len(split_sentences(p)) for p in paras]
    return {
        "n_para": len(paras),
        "para_char": desc(plen),
        "para_sent": desc(psent),
        "single_sent_para_ratio": sum(1 for x in psent if x == 1) / len(paras),
        "long_para_ratio": sum(1 for x in plen if x > 300) / len(paras),
        "para_char_hist": hist(plen, 50),
    }


def chapter_stats(chapters_text: Optional[List[str]]) -> dict:
    """章节数、章节长度分布。"""
    if not chapters_text:
        return {}
    clen = [char_count(c) for c in chapters_text]
    return {
        "n_chapter": len(chapters_text),
        "chapter_char": desc(clen),
        "chapter_len_hist": hist(clen, 1000),
    }


def compute(text: str, chapters_text: Optional[List[str]] = None) -> dict:
    """A 档基础统计。"""
    paras = split_paragraphs(text)
    sents = split_sentences(text)
    out = {
        "char_count": char_count(text),
        "word_count": word_count(text),
        "sentence": sentence_stats(sents),
        "paragraph": paragraph_stats(paras),
    }
    if chapters_text:
        out["chapter"] = chapter_stats(chapters_text)
    return out