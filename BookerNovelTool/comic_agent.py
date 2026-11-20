# -*- coding: utf-8 -*-
"""封装 comic 子命令的全部 LLM 调用。"""

import json
import logging
import os
from os import path
from typing import Type

import json_repair
from pydantic import BaseModel, parse_obj_as

from .comic_models import (
    GameState, NovelGameAssets, WorldChange, Worldbook,
)
from .comic_pmt import (
    EXTRACT_ASSETS_PMT, RUNTIME_PMT, SUMMARIZE_PMT,
)
from .openai import OpenAIClient
from .util import (
    gen_objs_md5, json_dump_model, read_yaml_model, render_prompt,
    write_yaml_model, ext_code_block, ext_cont_block,
)

logger = logging.getLogger(__name__)


class ComicAgent:
    """统一封装“小说 → 文字游戏”的结构化 LLM 调用。

    每个大模型调用实现为其中的一个方法，复用 comic_pmt.py 的提示词
    与 comic_models.py 的 Pydantic 模型。
    """

    def __init__(self, args):
        self.args = args
        self.model = args.model
        self.asset_dir = path.join(getattr(args, 'output', '') or '.', 'asset')
        self.llm = OpenAIClient.from_args(args)

    @staticmethod
    def _json_parse(raw: str, model: Type[BaseModel]):
        return parse_obj_as(model, json_repair.loads(ext_code_block(raw)))

    @staticmethod
    def _str_ctx(ctx: dict) -> dict:
        """把 ctx 中的 pydantic 模型序列化为 JSON 字符串，用于缓存命中和渲染。"""
        return {
            k: json_dump_model(v) if isinstance(v, BaseModel) else v
            for k, v in ctx.items()
        }

    def _call_json(
        self, pmt: str, model: Type[BaseModel], key: str, **ctx
    ) -> BaseModel:
        """渲染提示词，发起带 YAML 文件缓存的结构化 LLM 调用。"""
        ctx = self._str_ctx(ctx)
        cache_fname = path.join(self.asset_dir, key + '_' + gen_objs_md5(ctx) + '.yaml')
        r = read_yaml_model(cache_fname, model)
        if r is not None:
            return r
        ques = render_prompt(pmt, **ctx)
        res = self.llm.ask_chatgpt_retry(
            ques, self.model, self.args,
            parse_output=lambda s: self._json_parse(s, model),
        )
        write_yaml_model(cache_fname, res)
        return res

    # ── 步骤 1：离线解构 ──────────────────────────────────

    def extract_assets(self, novel_text: str) -> NovelGameAssets:
        """把小说文本解构为世界书 + 初始状态（带 YAML 文件缓存）。"""
        return self._call_json(
            EXTRACT_ASSETS_PMT, NovelGameAssets, 'extract_assets',
            novel_text=novel_text,
        )

    # ── 步骤 2：运行时单回合 ────────────────────────────────

    def runtime_turn(
        self,
        worldbook: Worldbook,
        state: GameState,
        rolling_summary: str,
        recent_history: str,
        player_input: str,
    ) -> WorldChange:
        """单回合运行时：上下文组装 → 结构化 LLM 输出 → 世界变更指令。

        每回合状态不同，不做文件缓存。
        """
        ques = render_prompt(
            RUNTIME_PMT,
            worldbook=json_dump_model(worldbook),
            state=json_dump_model(state),
            rolling_summary=rolling_summary,
            recent_history=recent_history,
            player_input=player_input,
        )
        return self.llm.ask_chatgpt_retry(
            ques, self.model, self.args,
            parse_output=lambda s: self._json_parse(s, WorldChange),
        )

    # ── 步骤 3：滚动摘要 ───────────────────────────────────

    def summarize_history(self, rolling_summary: str, history: str) -> str:
        """将新增历史压缩进当前滚动摘要（不缓存，返回纯文本）。"""
        ques = render_prompt(
            SUMMARIZE_PMT,
            rolling_summary=rolling_summary,
            history=history,
        )
        return self.llm.ask_chatgpt_retry(
            ques, self.model, self.args,
            parse_output=ext_cont_block,
        )
