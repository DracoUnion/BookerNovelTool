# -*- coding: utf-8 -*-
"""gal 运行时引擎：纯 Python 状态机、记忆组装、回合校验（不直接调 LLM）。

世界真实状态由本引擎维护，LLM 只提出叙事与变更建议；所有状态变更
在此处硬校验后显式应用，非法变更丢弃并记 warning。
"""

import json
import logging
from typing import List, Optional, Tuple

from .gal_models import AssetsBundle, GameState, TurnResult

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_BUDGET = 2000  # 近似 token 数，固定上下文预留 20% 余量给新输入与摘要


def estimate_tokens(text: str) -> int:
    """估算文本 token 数：优先 tiktoken，否则 len(text)//2 近似。"""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 2)


class GameEngine:
    """状态机：WorldBook 只读，GameState 由 Python 显式更新。"""

    def __init__(
        self,
        assets: AssetsBundle,
        state: Optional[GameState] = None,
        memory_budget: int = DEFAULT_MEMORY_BUDGET,
    ):
        self.assets = assets
        self.worldbook = assets.worldbook
        self.scenes = assets.scenes
        self.state = state or assets.initial_state
        self.memory_budget = memory_budget
        self.location_index = {loc.id: loc for loc in self.worldbook.locations}
        self.char_index = {ch.id: ch for ch in self.worldbook.characters}

    # ── 记忆组装（每轮，任务书 §7 分层）──────────────────────

    def assemble_context(self, player_input: str) -> dict:
        """组装导演上下文：滚动摘要 → 当前地点+在场角色卡 → 状态摘要 → 玩家输入。"""
        loc = self.location_index.get(self.state.player_location)
        present_cards = [
            self.char_index[cid]
            for cid in self.state.present_characters
            if cid in self.char_index
        ]
        state_summary = (
            f"位置：{self.state.player_location}"
            + (f"（{loc.name}）" if loc else "（未知地点）")
            + f"；背包：{', '.join(self.state.inventory) or '空'}"
            + f"；标志：{dict(self.state.flags)}"
            + f"；关系：{ {k: round(v, 2) for k, v in self.state.relationships.items()} }"
        )
        return {
            'worldbook': self.worldbook,
            'state': self.state,
            'rolling_summary': self.state.rolling_summary,
            'state_summary': state_summary,
            'present_characters': present_cards,
            'location': loc,
            'player_input': player_input,
        }

    def fixed_context_tokens(self, player_input: str = '') -> int:
        """固定上下文（不含逐字历史窗口）的近似 token 数。"""
        cards = ' '.join(
            ch.name + ' ' + ch.description for ch in [
                self.char_index[cid] for cid in self.state.present_characters if cid in self.char_index
            ]
        )
        text = (
            self.state.rolling_summary
            + ' | '
            + self.state.player_location
            + ' | '
            + cards
            + ' | '
            + json.dumps(dict(self.state.flags), ensure_ascii=False)
            + ' | '
            + player_input
        )
        return estimate_tokens(text)

    def recent_history_text(self, history_window: List[str]) -> str:
        """最近 K 轮逐字历史（新至旧，填满历史预算为止）。"""
        budget_for_history = int(self.memory_budget * 0.6)
        total = 0
        chosen: List[str] = []
        for entry in reversed(history_window):
            entry_tokens = estimate_tokens(entry)
            if total + entry_tokens > budget_for_history and chosen:
                break
            chosen.append(entry)
            total += entry_tokens
        chosen.reverse()
        return '\n'.join(chosen)

    def fold_history_if_needed(
        self,
        history_window: List[str],
        player_input: str,
        summarize_fn,
    ) -> List[str]:
        """若固定上下文 + 历史窗口超预算，用 summarize_fn 折叠旧历史。"""
        if not history_window:
            return history_window
        threshold = int(self.memory_budget * 0.8)
        total = self.fixed_context_tokens(player_input) + sum(
            estimate_tokens(e) for e in history_window
        )
        if total <= threshold:
            return history_window
        split = len(history_window) // 2 or 1
        old_part = '\n'.join(history_window[:split])
        result = summarize_fn(self.state.rolling_summary, old_part)
        summary = result.summary if hasattr(result, 'summary') else str(result)
        self.state.rolling_summary = summary
        logger.info('  滚动摘要已更新（折叠 %d 轮旧历史）', split)
        return history_window[split:]

    # ── 状态变更校验与应用（Python 侧硬规则）─────────────────

    def apply(self, turn_result: TurnResult) -> Tuple[bool, List[str]]:
        """校验并应用 TurnResult 到 GameState。返回 (是否全合法, 警告列表)。

        校验规则：
        - scene_change 目标地点必须存在于世界书，否则丢弃；
        - item_delta add 的物品必须在当前地点或背包中，remove 必须在背包中；
        - relationship_delta 裁剪到 [-1, 1]；
        - 非法字段不进入 GameState。
        """
        warnings: List[str] = []

        if turn_result.scene_change is not None:
            if turn_result.scene_change in self.location_index:
                self.state.player_location = turn_result.scene_change
            else:
                warnings.append(
                    f"scene_change '{turn_result.scene_change}' 不存在于世界书地点，已忽略"
                )

        if turn_result.item_delta:
            loc = self.location_index.get(self.state.player_location)
            loc_items = set(loc.items) if loc else set()
            for item in turn_result.item_delta.get('add', []) or []:
                if item in loc_items or item in self.state.inventory:
                    if item not in self.state.inventory:
                        self.state.inventory.append(item)
                else:
                    warnings.append(
                        f"物品 '{item}' 不在当前地点或背包中，add 已忽略"
                    )
            for item in turn_result.item_delta.get('remove', []) or []:
                if item in self.state.inventory:
                    self.state.inventory.remove(item)
                else:
                    warnings.append(
                        f"物品 '{item}' 不在背包中，remove 已忽略"
                    )

        if turn_result.relationship_delta:
            for entry in turn_result.relationship_delta:
                char_id = entry.get('char_id') if isinstance(entry, dict) else None
                delta = float(entry.get('delta', 0.0) if isinstance(entry, dict) else 0.0)
                if not char_id or char_id not in self.char_index:
                    warnings.append(
                        f"关系目标 '{char_id}' 不存在，已忽略"
                    )
                    continue
                new_val = max(
                    -1.0, min(1.0, self.state.relationships.get(char_id, 0.0) + delta)
                )
                self.state.relationships[char_id] = round(new_val, 2)

        if turn_result.flag_update:
            self.state.flags.update(turn_result.flag_update)

        self.state.game_over = bool(turn_result.game_over)
        self.state.turn += 1
        return (len(warnings) == 0), warnings
