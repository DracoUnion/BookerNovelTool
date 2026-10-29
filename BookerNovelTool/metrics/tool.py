#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""metrics 子命令：编排器与命令行入口。

命名约定：`reg_subparser` 在 `BookerNovelTool.__main__` 中调用，
CLI 入口函数实例化 `MetricsOrchestrator` 并运行。
"""

import argparse
import json
import logging
import os
from os import path

from ..novel_anls import extract_text_from_epub
from ..util import read_text, write_text
from .common import Budget
from .metrics_agent import MetricsAgent
from .pipeline import compute_report

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def _load_input(fname: str):
    """加载输入：EPUB / 单文件 / 章节目录，返回 (text, chapters_text, titles)。"""
    if path.isdir(fname):
        files = sorted(
            f for f in os.listdir(fname)
            if f.endswith(('.txt', '.md')) and not f.startswith('.')
        )
        if not files:
            logger.fatal(f'目录 {fname} 中没有 .txt/.md 文件')
            return None, None, None
        chapters = []
        titles = []
        for f in files:
            text = read_text(path.join(fname, f))
            if text:
                chapters.append(text)
                titles.append(os.path.splitext(f)[0])
        return '\n\n'.join(chapters), chapters, titles

    if fname.endswith('.epub'):
        chapters = [
            c for c in extract_text_from_epub(fname)
            if c and c.text
        ]
        text = '\n\n'.join(c.text for c in chapters)
        titles = [c.title for c in chapters]
        return text, chapters, titles

    text = read_text(fname)
    if not text:
        logger.fatal(f'无法读取文件 {fname}')
        return None, None, None
    return text, None, None


class MetricsOrchestrator:
    """编排 A/B/C/D 四档指标计算并输出报告。"""

    def __init__(self, args, **kw):
        self.args = args
        self.budget = Budget(args.budget)
        self.agent = MetricsAgent(args) if args.tier in ('c', 'all', 'd') else None
        self.report = {}

    def load(self):
        text, chapters, titles = _load_input(self.args.fname)
        self.text = text
        self.chapters = chapters
        self.titles = titles
        if not text:
            raise SystemExit(1)
        logger.info(
            f'已加载 {self.args.fname}：'
            f'{len(self.chapters) if self.chapters else "N/A"} 章，'
            f'{len(text)} 字'
        )

    def compute(self):
        baseline = None
        if self.args.baseline:
            baseline = read_text(self.args.baseline)
            if not baseline:
                logger.warning(f'无法读取基准文本 {self.args.baseline}')
        self.report = compute_report(
            self.text,
            agent=self.agent,
            chapters_text=self.chapters,
            titles=self.titles,
            tier=self.args.tier,
            budget=self.budget,
            baseline=baseline,
            use_pos=not self.args.no_pos,
            use_lexicon=not self.args.no_lexicon,
            use_topic=not self.args.no_topic,
            use_cohesion=not self.args.no_cohesion,
            use_phonetic=not self.args.no_phonetic,
        )

    @staticmethod
    def _tier_name(tier: str) -> str:
        return {'ab': 'A+B 档', 'c': 'C 档', 'd': 'D 档', 'all': 'A/B/C/D 档'}[tier]

    def save(self):
        out = {
            "meta": {
                "source": self.args.fname,
                "tier": self.args.tier,
                "budget": {"max_calls": self.budget.max_calls, "calls": self.budget.calls},
            },
            **self.report,
        }
        fname = self.args.output
        os.makedirs(path.dirname(fname) or '.', exist_ok=True)
        with open(fname, 'w', encoding='utf-8') as file:
            json.dump(out, file, ensure_ascii=False, indent=2)
        logger.info(f'报告已保存至 {fname}')

    def run(self):
        self.load()
        logger.info(f'开始计算 {self._tier_name(self.args.tier)}...')
        self.compute()
        self.save()


def metrics(args):
    """metrics 子命令入口函数。"""
    MetricsOrchestrator(args).run()


def reg_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser(
        "metrics", help="小说风格/质量评价指标（A/B/C/D 四档）",
    )
    parser.add_argument("fname", help="文本/EPUB 文件，或章节文本目录")
    parser.add_argument("-o", "--output", default="metrics_report.json",
                        help="报告输出路径（默认 metrics_report.json）")
    parser.add_argument("-a", "--asset-dir", default=".metrics_cache",
                        help="LLM 结果缓存目录（默认 .metrics_cache）")
    parser.add_argument("--tier", choices=("ab", "c", "d", "all"), default="all",
                        help="计算档位（默认 all）")
    parser.add_argument("--budget", type=int, default=5000,
                        help="LLM 调用预算上限（默认 5000）")
    parser.add_argument("--max-chars", type=int, default=4000,
                        help="单次 LLM 调用截取的文本长度（默认 4000）")
    parser.add_argument("--baseline", default=None,
                        help="用于风格相似度对比的基准文本文件")
    parser.add_argument("--no-pos", action="store_true",
                        help="跳过 B 档词法句法（hanlp）")
    parser.add_argument("--no-lexicon", action="store_true",
                        help="跳过 B 档词典类指标")
    parser.add_argument("--no-topic", action="store_true",
                        help="跳过 B 档主题网络（gensim/networkx）")
    parser.add_argument("--no-cohesion", action="store_true",
                        help="跳过 B 档衔接连贯（hanlp）")
    parser.add_argument("--no-phonetic", action="store_true",
                        help="跳过 A 档语音特征（pypinyin）")
    parser.set_defaults(func=metrics)