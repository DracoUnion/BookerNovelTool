# -*- coding: utf-8 -*-
"""封装 gal 子命令的全部 LLM 调用。"""

import json
import logging
import os
from os import path
from typing import List, Optional, Type

import json_repair
from pydantic import BaseModel, Field, parse_obj_as

from .gal_models import (
    AssetsBundle, CharacterCard, GameState, Location, Scene, SummaryResult, TurnResult, WorldBook,
)
from .gal_pmt import (
    PMT_EXTRACT_CHARACTERS,
    PMT_EXTRACT_LOCATIONS,
    PMT_EXTRACT_SCENES,
    PMT_MERGE_ENTITIES,
    PMT_RUNTIME_DIRECTOR,
    PMT_RUNTIME_SUMMARY,
)
from .openai import OpenAIClient
from .util import (
    gen_objs_md5, json_dump_model, md5, read_yaml_model, render_prompt,
    write_yaml_model, ext_code_block,
)

logger = logging.getLogger(__name__)


# ── LLM 抽取输出的轻量包装模型（提示词输出为带键的 JSON 对象）────


class _CharactersOut(BaseModel):
    characters: List[CharacterCard] = Field(default_factory=list, description="抽取出的角色卡列表")


class _ScenesOut(BaseModel):
    scenes: List[Scene] = Field(default_factory=list, description="抽取出的场景列表")


class _LocationsOut(BaseModel):
    locations: List[Location] = Field(default_factory=list, description="抽取出的地点列表")


class _WorldBookOut(BaseModel):
    title: str = Field(..., description="小说标题")
    characters: List[CharacterCard] = Field(default_factory=list, description="合并后的角色卡")
    locations: List[Location] = Field(default_factory=list, description="合并后的地点")
    rules: List[str] = Field(default_factory=list, description="世界硬规则")
    factions: List[str] = Field(default_factory=list, description="势力")


class GalAgent:
    """统一封装“小说 → 文字游戏”的结构化 LLM 调用。

    每个大模型调用实现为其中的一个方法，复用 gal_pmt.py 的提示词
    与 gal_models.py 的 Pydantic 模型。
    """

    def __init__(self, args):
        self.args = args
        self.model = args.model
        self.asset_dir = path.join(
            getattr(args, 'out', '') or getattr(args, 'output', '') or '.', 'asset',
        )
        self.llm = OpenAIClient.from_args(args)
        # 结构化 JSON 输出对流式/思考模式极易碎（空 content / thinking 标签污染 JSON），
        # 强制关闭，其余参数仍由命令行参数控制（见系统 memory：LLM 调用需 -ST -TN）。
        self.llm.stream = False
        self.llm.no_think = True

    @staticmethod
    def _json_obj(raw: str):
        """把模型输出（可能被 ```json ... ``` 包裹）修复为 JSON 数据。"""
        try:
            candidate = ext_code_block(raw)
        except AttributeError:
            candidate = raw
        return json_repair.loads(candidate)

    def _str_ctx(self, ctx: dict) -> dict:
        """把 ctx 中的 pydantic 模型序列化为 JSON 字符串，用于缓存命中和渲染。"""
        return {
            k: json_dump_model(v) if isinstance(v, BaseModel) else v
            for k, v in ctx.items()
        }

    def _call_structured(
        self, pmt: str, schema: Type[BaseModel], key: Optional[str], **ctx
    ) -> BaseModel:
        """渲染提示词，发起结构化 LLM 调用；parse 步骤带 YAML 文件缓存。

        key 为 None 时不做缓存（运行时每回合状态不同，不宜缓存）。
        """
        ctx = self._str_ctx(ctx)
        cache_fname = None
        if key:
            cache_fname = path.join(
                self.asset_dir, key + '_' + gen_objs_md5(ctx) + '.yaml'
            )
            cached = read_yaml_model(cache_fname, schema)
            if cached is not None:
                return cached
        ques = render_prompt(pmt, **ctx)
        res = self.llm.call_llm_structured(
            ques,
            self.model,
            schema,
            retry=getattr(self.args, 'retry', 3),
            temp=getattr(self.args, 'temp', 1.0),
        )
        if cache_fname:
            write_yaml_model(cache_fname, res)
        return res

    # ── 步骤 1：离线解构（每章并发，结果带 YAML 缓存）──────────

    def extract_characters(self, chapter_text: str, chapter_index: int) -> List[CharacterCard]:
        """章节 → 角色卡列表（PMT_EXTRACT_CHARACTERS，温度 0.2）。"""
        result = self._call_structured(
            PMT_EXTRACT_CHARACTERS, _CharactersOut, 'extract_characters',
            chapter_text=chapter_text, chapter_index=chapter_index,
        )
        return result.characters

    def extract_scenes(self, chapter_text: str, chapter_index: int) -> List[Scene]:
        """章节 → 场景列表（PMT_EXTRACT_SCENES，温度 0.2，强完整性规则）。"""
        result = self._call_structured(
            PMT_EXTRACT_SCENES, _ScenesOut, 'extract_scenes',
            chapter_text=chapter_text, chapter_index=chapter_index,
        )
        return result.scenes

    def extract_locations(self, chapter_text: str, chapter_index: int) -> List[Location]:
        """章节 → 地点列表（PMT_EXTRACT_LOCATIONS，温度 0.2）。"""
        result = self._call_structured(
            PMT_EXTRACT_LOCATIONS, _LocationsOut, 'extract_locations',
            chapter_text=chapter_text, chapter_index=chapter_index,
        )
        return result.locations

    def merge_entities(
        self,
        full_text: str,
        chapter_characters: List[List[CharacterCard]],
        chapter_locations: List[List[Location]],
    ) -> WorldBook:
        """跨章去重合并角色/地点，产出世界书（PMT_MERGE_ENTITIES，温度 0.1）。"""
        result = self._call_structured(
            PMT_MERGE_ENTITIES, _WorldBookOut, 'merge_entities',
            full_text=full_text,
            chapter_characters=json_dump_model(chapter_characters),
            chapter_locations=json_dump_model(chapter_locations),
        )
        return WorldBook(
            title=result.title,
            source_hash=md5(full_text),
            characters=result.characters,
            locations=result.locations,
            rules=result.rules,
            factions=result.factions,
        )

    # ── 步骤 2：运行时单回合（不缓存，每回合状态不同）──────────

    def director_turn(
        self,
        worldbook: WorldBook,
        state: GameState,
        rolling_summary: str,
        recent_history: str,
        player_input: str,
        validation_feedback: str = '',
        temperature: Optional[float] = None,
    ) -> TurnResult:
        """导演单回合：上下文组装 → 结构化 LLM 输出 TurnResult（温度 0.7）。"""
        ques = render_prompt(
            PMT_RUNTIME_DIRECTOR,
            worldbook=json_dump_model(worldbook),
            state=json_dump_model(state),
            rolling_summary=rolling_summary,
            recent_history=recent_history,
            player_input=player_input,
            validation_feedback=validation_feedback,
        )
        return self.llm.call_llm_structured(
            ques,
            self.model,
            TurnResult,
            retry=getattr(self.args, 'retry', 3),
            temp=temperature if temperature is not None else getattr(self.args, 'temp', 0.7),
        )

    def summarize_history(self, rolling_summary: str, history: str) -> SummaryResult:
        """滚动摘要压缩（PMT_RUNTIME_SUMMARY，温度 0.3，不缓存）。"""
        ques = render_prompt(
            PMT_RUNTIME_SUMMARY,
            rolling_summary=rolling_summary,
            history=history,
        )
        return self.llm.call_llm_structured(
            ques,
            self.model,
            SummaryResult,
            retry=getattr(self.args, 'retry', 3),
            temp=0.3,
        )
