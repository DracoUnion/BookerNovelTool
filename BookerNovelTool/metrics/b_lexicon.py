#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""B 档：词典类指标（情感/六感/颜色/声音/气味/味道/空间/时间/数量/风格词）。

内置小词典用于演示；生产环境可替换为权威词典。支持传入自定义词典。
"""

from collections import Counter
from typing import Dict, List, Optional

from .common import tokenize

POS_WORDS = set(
    "喜悦 快乐 幸福 温暖 希望 爱 美 好 赞 勇敢 坚强 温柔 宁静 明亮".split()
)
NEG_WORDS = set(
    "悲伤 痛苦 愤怒 恐惧 绝望 恨 丑 恶 孤独 寒冷 黑暗 死亡 哭 泪".split()
)
SENSE = {
    "visual": set("看 望 见 色 光 亮 暗 红 蓝 绿 白 黑 黄 紫 灰 影 彩".split()),
    "audio": set("听 声 响 音 噪 静 吵 喊 叫 哭 笑 唱 吼 叹".split()),
    "touch": set("触 摸 冷 热 暖 凉 硬 软 粗 滑 痛 痒 麻".split()),
    "smell": set("闻 香 臭 味 气 嗅".split()),
    "taste": set("尝 甜 苦 酸 辣 咸 鲜 涩".split()),
    "body": set("累 饿 渴 困 疼 酸 麻 胀 晕 喘".split()),
}
COLOR = set("红 橙 黄 绿 青 蓝 紫 黑 白 灰 粉 褐 金 银".split())
SOUND = set("响 声 音 噪 静 吵 喊 叫 哭 笑 唱 吼 叹 轰 隆 叮 咚".split())
SMELL = set("香 臭 味 气 嗅 芳 腥 膻".split())
TASTE = set("甜 苦 酸 辣 咸 鲜 涩 淡 腻".split())
SPACE = set("上 下 左 右 前 后 里 外 东 西 南 北 中 间 旁 边 远 近".split())
TIME = set("年 月 日 时 分 秒 春 夏 秋 冬 早 晚 昨 今 明 古 今".split())
QUANT = set(
    "一 二 三 四 五 六 七 八 九 十 百 千 万 亿 些 个 只 条 张 片 群 堆".split()
)
CLASSICAL = set("之 乎 者 也 矣 焉 哉 乃 遂 亦 其 此 彼 何 莫 弗 勿".split())
NETWORK = set("yyds 绝绝子 破防 emo 内卷 躺平 打call 真香 社死 栓Q".split())
SLANG = set("哥们 家伙 老板 大佬 老铁 兄弟".split())
DIALECT = set("俺 咱 啥 咋 嘞 咯 嘛 咧 啦".split())
HONORIFIC = set("您 请 劳驾 拜托 赐教 久仰 光临 惠顾".split())
PROFANITY = set("操 靠 妈的 混蛋 王八蛋 该死".split())
PROFESSIONAL = set("算法 模型 数据 系统 协议 接口 架构 芯片 量子 基因 熵".split())


def _ratio(tokens: List[str], dict_set) -> float:
    c = Counter(tokens)
    n = len(tokens) or 1
    return sum(c[w] for w in dict_set if w in c) / n


def compute(text: str, user_dicts: Optional[Dict[str, List[str]]] = None) -> dict:
    """B 档词典类指标。"""
    toks = tokenize(text)
    n = len(toks) or 1
    tc = Counter(toks)
    pos_hit = sum(tc[w] for w in POS_WORDS if w in tc)
    neg_hit = sum(tc[w] for w in NEG_WORDS if w in tc)
    total_emo = pos_hit + neg_hit or 1
    sense = {k: _ratio(toks, ws) for k, ws in SENSE.items()}
    out = {
        "emotion_word_density": total_emo / n,
        "positive_ratio": pos_hit / total_emo,
        "negative_ratio": neg_hit / total_emo,
        "sensory": sense,
        "sensory_total": sum(sense.values()),
        "color_density": _ratio(toks, COLOR),
        "sound_density": _ratio(toks, SOUND),
        "smell_density": _ratio(toks, SMELL),
        "taste_density": _ratio(toks, TASTE),
        "space_density": _ratio(toks, SPACE),
        "time_density": _ratio(toks, TIME),
        "quantity_density": _ratio(toks, QUANT),
        "classical_density": _ratio(toks, CLASSICAL),
        "network_density": _ratio(toks, NETWORK),
        "slang_density": _ratio(toks, SLANG),
        "dialect_density": _ratio(toks, DIALECT),
        "honorific_density": _ratio(toks, HONORIFIC),
        "profanity_density": _ratio(toks, PROFANITY),
        "professional_density": _ratio(toks, PROFESSIONAL),
        "avg_word_len": sum(len(t) for t in toks) / n,
    }
    if user_dicts:
        for name, words in user_dicts.items():
            out[f"{name}_density"] = _ratio(toks, set(words))
    return out