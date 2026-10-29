#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：词法句法（词性分布/实虚比/人称/依存距离/NER/句首尾词类）。

依赖 hanlp（重型 DL 模型）；未安装时降级为 available=False。
"""

import re
from collections import Counter
from typing import List

import numpy as np

POS_MAP = {
    "名词": {"NN", "NR", "NS", "NT", "NZ", "N"},
    "动词": {"VV", "VA", "VC", "VE", "V", "VB"},
    "形容词": {"JJ", "A"},
    "副词": {"RB", "AD", "D"},
    "代词": {"PN", "PRP", "R"},
    "介词": {"IN", "P"},
    "连词": {"CC", "CS", "C"},
    "助词": {"DEC", "DEG", "DER", "DEV", "AS", "SP", "U"},
    "叹词": {"IJ", "I"},
    "拟声词": {"ON", "O"},
}

FIRST_PRON = {"我", "我们", "咱", "咱们"}
SECOND_PRON = {"你", "您", "你们"}
THIRD_PRON = {"他", "她", "它", "他们", "她们", "它们"}

_nlp = None


def _load():
    """惰性加载 hanlp 预训练模型。"""
    global _nlp
    if _nlp is None:
        import hanlp

        _nlp = hanlp.load(
            hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH
        )
    return _nlp


def compute(text: str, max_chars: int = None) -> dict:
    """B 档词法句法统计；max_chars 限制处理文本长度以控制耗时。"""
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    try:
        nlp = _load()
        doc = nlp(text)
    except Exception as e:
        return {"available": False, "error": str(e)}

    toks = doc.get("tok/fine") or []
    pos = doc.get("pos/ctb") or []
    n = len(pos) or 1
    pos_cnt = Counter(pos)
    pos_ratio = {
        name: sum(v for k, v in pos_cnt.items() if k in tags) / n
        for name, tags in POS_MAP.items()
    }
    content_tags = (
        POS_MAP["名词"] | POS_MAP["动词"] | POS_MAP["形容词"] | POS_MAP["副词"]
    )
    content = sum(v for k, v in pos_cnt.items() if k in content_tags)
    mod = sum(
        v for k, v in pos_cnt.items()
        if k in POS_MAP["形容词"] | POS_MAP["副词"]
    )
    verb = sum(v for k, v in pos_cnt.items() if k in POS_MAP["动词"]) or 1
    # 人称
    pc = Counter(t for t, p in zip(toks, pos) if p in POS_MAP["代词"])
    first = sum(v for k, v in pc.items() if k in FIRST_PRON)
    second = sum(v for k, v in pc.items() if k in SECOND_PRON)
    third = sum(v for k, v in pc.items() if k in THIRD_PRON)
    pt = sum(pc.values()) or 1
    # 依存距离
    dep = doc.get("dep") or []
    dists = [
        abs((i + 1) - head)
        for i, (head, _rel) in enumerate(dep)
        if head and head != 0
    ]
    # NER
    ner = doc.get("ner/msra") or []
    ner_cnt = Counter(e[1] for e in ner)
    # 句首/句尾词类（仅前 50 句，避免逐句重算过慢）
    head_pos, tail_pos = Counter(), Counter()
    for s in re.split(r'[。！？!?…]', text)[:50]:
        s = s.strip()
        if not s:
            continue
        try:
            d = nlp(s)
            ps = d.get("pos/ctb") or []
            if ps:
                head_pos[ps[0]] += 1
                tail_pos[ps[-1]] += 1
        except Exception:
            pass
    return {
        "pos_ratio": pos_ratio,
        "content_func_ratio": content / max(n - content, 1),
        "content_density": content / n,
        "adjective_density": pos_ratio.get("形容词", 0),
        "adverb_density": pos_ratio.get("副词", 0),
        "modifier_verb_ratio": mod / max(verb, 1),
        "pronoun_ratio": pt / n,
        "person_1": first / pt,
        "person_2": second / pt,
        "person_3": third / pt,
        "dep_mean_distance": float(np.mean(dists)) if dists else 0.0,
        "dep_max_distance": int(np.max(dists)) if dists else 0,
        "ner_counts": dict(ner_cnt),
        "ner_density": sum(ner_cnt.values()) / n,
        "sent_head_pos": dict(head_pos),
        "sent_tail_pos": dict(tail_pos),
    }