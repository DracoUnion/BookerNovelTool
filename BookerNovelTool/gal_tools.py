# -*- coding: utf-8 -*-
"""gal 子命令工具循环：将阶段性步骤暴露为可被 LLM 工具调用的 tool_* 方法。

遵循 AGENTS.md“为子命令添加工具”章节：
- 工具类继承 ToolsMixin
- 每个步骤实现为 tool_* 方法
- 具有 _TOOL_PARAMS 类属性，描述所有 tool_* 方法的参数 Schema
- 方法带文件缓存：read_yaml_model 加载，非空则返回；调用大模型后 write_yaml_model 保存
"""

import json
import logging
import os
from os import path
from typing import Any, Dict, List, Optional, Type

import yaml
from pydantic import BaseModel, parse_obj_as

from .gal_agent import GalAgent
from .gal_models import AssetsBundle, GameState, TurnResult, ValidationResult, WorldBook
from .gal_pmt import PMT_VALIDATE_CHANGE
from .util import (
    gen_objs_md5, json_dump_model, md5, read_text, read_yaml_model,
    render_prompt, write_yaml_model,
)

logger = logging.getLogger(__name__)


# ── 基类：文件缓存的工具混入 ─────────────────────────────────


class ToolsMixin:
    """轻量工具混入：提供基于 YAML 文件的缓存读写能力。"""

    def __init__(self, args):
        self.args = args
        self.asset_dir = path.join(
            getattr(args, 'out', '') or getattr(args, 'output', '') or '.', 'asset',
        )

    def _cached_call(
        self,
        key: str,
        ctx: dict,
        model: Type[BaseModel],
        call_fn,
    ) -> BaseModel:
        """文件缓存：命中则返回缓存，否则执行 call_fn 并写入缓存。"""
        ctx_str = {
            k: json_dump_model(v) if isinstance(v, BaseModel) else v
            for k, v in ctx.items()
        }
        cache_fname = path.join(
            self.asset_dir, key + '_' + gen_objs_md5(ctx_str) + '.yaml'
        )
        cached = read_yaml_model(cache_fname, model)
        if cached is not None:
            return cached
        res = call_fn()
        write_yaml_model(cache_fname, res)
        return res


# ── 工具类：把阶段性步骤暴露为 tool_* 方法 ──────────────────


class GalTools(ToolsMixin):
    """gal 阶段性工具集：tool_* 方法可被 LLM 工具调用循环直接调用。"""

    def __init__(self, agent: GalAgent):
        # ToolsMixin 需要 args；从 agent 复用
        super().__init__(agent.args)
        self.agent = agent

    # _TOOL_PARAMS：所有 tool_* 方法的参数 Schema（供工具调用循环校验入参）
    _TOOL_PARAMS: Dict[str, Any] = {
        'tool_approve_worldbook': {
            'description': '人工审批世界书：确认后继续保存完整资产包，拒绝则仅保留 worldbook.json',
            'parameters': {
                'type': 'object',
                'properties': {
                    'confirm': {
                        'type': 'boolean',
                        'description': '是否确认 worldbook，true 继续，false 停止',
                    },
                },
                'required': ['confirm'],
            },
        },
        'tool_validate_assets': {
            'description': '对资产包做~13项确定性验收，返回通过/失败清单',
            'parameters': {
                'type': 'object',
                'properties': {
                    'assets_dir': {
                        'type': 'string',
                        'description': '资产包目录（含 worldbook/scenes/initial_state/manifest）',
                    },
                },
                'required': ['assets_dir'],
            },
        },
        'tool_export_save': {
            'description': '导出当前运行时存档为 JSON，包含状态与 history_window',
            'parameters': {
                'type': 'object',
                'properties': {
                    'save_path': {
                        'type': 'string',
                        'description': '存档输出路径',
                    },
                    'state_json': {
                        'type': 'string',
                        'description': 'GameState 的 JSON 字符串',
                    },
                    'history_json': {
                        'type': 'string',
                        'description': '历史窗口的 JSON 字符串',
                    },
                    'assets_hash': {
                        'type': 'string',
                        'description': '资产包 source_hash',
                    },
                },
                'required': ['save_path', 'state_json'],
            },
        },
    }

    # ── tool_approve_worldbook ──────────────────────────────

    def tool_approve_worldbook(self, confirm: bool) -> dict:
        """审批世界书：confirm=True 继续保存，False 停止。"""
        if confirm:
            return {'approved': True, 'detail': 'worldbook 已确认，继续保存资产包'}
        return {'approved': False, 'detail': '用户未确认 worldbook，停止于审批阶段'}

    # ── tool_validate_assets ────────────────────────────────

    def tool_validate_assets(self, assets_dir: str) -> dict:
        """对资产包做~13项确定性验收，返回通过/失败清单。"""
        from .gal_models import AssetsBundle, WorldBook

        wb_text = read_text(path.join(assets_dir, 'worldbook.json'))
        scenes_text = read_text(path.join(assets_dir, 'scenes.json'))
        state_text = read_text(path.join(assets_dir, 'initial_state.json'))
        if not (wb_text and scenes_text and state_text):
            return {'valid': False, 'errors': ['资产包缺少 worldbook/scenes/initial_state']}

        from .gal_models import Scene

        wb = WorldBook(**json.loads(wb_text))
        scenes = [Scene(**s) for s in json.loads(scenes_text)]
        st = GameState(**json.loads(state_text))
        bundle = AssetsBundle(worldbook=wb, scenes=scenes, initial_state=st)

        # 复用 GalParseOrchestrator.step_validate_assets 的检查逻辑（精简内联）
        errors: List[str] = []
        loc_ids = {loc.id for loc in wb.locations}
        char_ids = {ch.id for ch in wb.characters}

        chapter_count = len({s.chapter for s in scenes}) or 1
        if len(scenes) < chapter_count * 4:
            errors.append(
                f'场景完整性不足：{len(scenes)} 个场景 < 章节数 {chapter_count} × 4'
            )

        name_count: Dict[str, int] = {}
        for ch in wb.characters:
            name_count[ch.name] = name_count.get(ch.name, 0) + 1
        dup_names = [name for name, c in name_count.items() if c > 1]
        if dup_names:
            errors.append(f'角色未去重：{dup_names}')

        for s in scenes:
            if s.location_id not in loc_ids:
                errors.append(f'场景{s.scene_number} 引用不存在的地点 {s.location_id}')
            for el in s.elements:
                if el.type not in {'action', 'dialogue', 'transition', 'reveal'}:
                    errors.append(f'场景{s.scene_number} 元素类型非法：{el.type}')
                if el.type == 'dialogue' and not el.speaker_id:
                    errors.append(f'场景{s.scene_number} 对话元素缺少 speaker_id')
            for cid in s.characters_present:
                if cid not in char_ids:
                    errors.append(f'场景{s.scene_number} 在场角色 {cid} 不存在于世界书')
            if not s.elements:
                errors.append(f'场景{s.scene_number} 空场景')

        if st.player_location not in loc_ids:
            errors.append(f'初始地点 {st.player_location} 不存在于世界书')
        for cid in st.present_characters:
            if cid not in char_ids:
                errors.append(f'初始在场角色 {cid} 不存在于世界书')
        all_loc_items = {item for loc in wb.locations for item in loc.items}
        for item in st.inventory:
            if item not in all_loc_items:
                errors.append(f'初始背包物品 {item} 不存在于任何地点')
        if not wb.rules:
            errors.append('世界书缺少硬规则（rules 为空）')

        manifest_text = read_text(path.join(assets_dir, 'manifest.json'))
        if manifest_text:
            try:
                manifest = json.loads(manifest_text)
                if manifest.get('source_hash') != wb.source_hash:
                    errors.append('manifest source_hash 与世界书不一致')
            except json.JSONDecodeError:
                pass

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'detail': (
                f'{len(scenes)} 场景，{len(wb.characters)} 角色，{len(wb.locations)} 地点'
            ),
        }

    # ── tool_export_save ────────────────────────────────────

    def tool_export_save(
        self,
        save_path: str,
        state_json: str,
        history_json: str = '[]',
        assets_hash: str = '',
    ) -> dict:
        """导出存档文件（SaveFile）。"""
        from .gal_models import GameState, SaveFile

        state = GameState(**json.loads(state_json))
        history = json.loads(history_json) if history_json else []
        save = SaveFile(
            state=state,
            history_window=history,
            assets_hash=assets_hash,
        )
        os.makedirs(path.dirname(save_path) or '.', exist_ok=True)
        with open(save_path, 'w', encoding='utf8') as f:
            json.dump(save.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        return {
            'exported': True,
            'save_path': save_path,
            'turn': state.turn,
            'history_count': len(history),
        }
