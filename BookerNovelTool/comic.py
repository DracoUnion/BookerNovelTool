import json
import logging
import os
from os import path
from typing import List

from .comic_agent import ComicAgent
from .comic_models import GameState, InitialGameState, NovelGameAssets, WorldChange, Worldbook
from .util import read_text, write_text

logger = logging.getLogger(__name__)

RECENT_TURNS = 5
SUMMARY_EVERY = 5


class ComicOrchestrator:
    """编排《任务书_Comic》的六层架构：离线解构资产 → 在线运行时游戏循环。

    固定流程：
      1. 加载小说文本
      2. 离线抽取游戏资产（世界书 + 初始状态）
      3. 保存资产到输出目录
      4. 初始化运行时状态
      5. 进入对话式游戏运行时：玩家输入 → 上下文组装 → LLM 叙事 → Python 更新状态
    """

    def __init__(self, args):
        self.args = args
        self.agent = ComicAgent(args)
        self.novel_path = args.novel
        self.output_dir = args.output or path.join(
            path.dirname(path.abspath(self.novel_path)),
            path.splitext(path.basename(self.novel_path))[0] + '_game',
        )
        os.makedirs(self.output_dir, exist_ok=True)

    # ── 步骤 1：加载小说 ──────────────────────────────────

    def step_load_novel(self) -> str:
        logger.info(f'📖 加载小说：{self.novel_path}')
        text = read_text(self.novel_path)
        if not text:
            logger.fatal(f'小说文件不存在或为空：{self.novel_path}')
            raise FileNotFoundError(self.novel_path)
        logger.info(f'  文本长度：{len(text)} 字')
        return text

    # ── 步骤 2：离线抽取游戏资产 ──────────────────────────

    def step_extract_assets(self, novel_text: str) -> NovelGameAssets:
        logger.info('🏗 步骤二：离线抽取游戏资产（世界书 + 初始状态）')
        assets = self.agent.extract_assets(novel_text)
        logger.info(
            f'  角色数：{len(assets.worldbook.characters)}，地点数：{len(assets.worldbook.locations)}，'
            f'物品数：{len(assets.worldbook.items)}，场景数：{len(assets.worldbook.scenes)}'
        )
        return assets

    # ── 步骤 3：保存资产 ──────────────────────────────────

    def step_save_assets(self, assets: NovelGameAssets) -> None:
        worldbook_fname = path.join(self.output_dir, 'worldbook.json')
        state_fname = path.join(self.output_dir, 'initial_state.json')
        write_text(worldbook_fname, json.dumps(assets.worldbook.model_dump(mode="json"), ensure_ascii=False, indent=2))
        write_text(state_fname, json.dumps(assets.initial_state.model_dump(mode="json"), ensure_ascii=False, indent=2))
        logger.info(f'💾 资产已保存：{worldbook_fname}, {state_fname}')

    # ── 步骤 4：初始化运行时状态 ───────────────────────────

    def step_init_state(self, assets: NovelGameAssets) -> GameState:
        state = GameState(
            location=assets.initial_state.location,
            inventory=list(assets.initial_state.inventory),
            present_characters=list(assets.initial_state.present_characters),
            flags=dict(assets.initial_state.flags),
        )
        logger.info(f'▶ 起始地点：{state.location}')
        return state

    # ── 状态变更（Python 侧显式应用，LLM 不直接改状态）─────

    @staticmethod
    def _apply_change(state: GameState, change: WorldChange) -> None:
        """把 LLM 下达的世界变更指令应用到 GameState。"""
        if change.scene_change:
            state.location = change.scene_change
        if change.inventory_delta:
            for item in change.inventory_delta.get('add', []) or []:
                if item not in state.inventory:
                    state.inventory.append(item)
            for item in change.inventory_delta.get('remove', []) or []:
                state.inventory = [i for i in state.inventory if i != item]
        if change.relationship_delta:
            for char_id, delta in change.relationship_delta.items():
                state.relationships[char_id] = round(state.relationships.get(char_id, 0.0) + delta, 2)
        if change.flags_delta:
            state.flags.update(change.flags_delta)

    # ── 步骤 5：运行时游戏循环 ─────────────────────────────

    def step_run_game(self, state: GameState, assets: NovelGameAssets) -> GameState:
        logger.info('🎮 步骤五：进入运行时游戏循环（输入 quit/exit 结束）')
        recent_history: List[str] = []
        while True:
            try:
                player_input = input('> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not player_input:
                continue
            if player_input.lower() in ('quit', 'exit', 'q'):
                print('游戏结束。')
                break

            recent_history.append(f'玩家：{player_input}')
            history_tail = '\n'.join(recent_history[-RECENT_TURNS:])

            change: WorldChange = self.agent.runtime_turn(
                assets.worldbook, state, state.rolling_summary, history_tail, player_input,
            )
            print(change.narration)

            self._apply_change(state, change)
            recent_history.append(f'世界：{change.narration}')
            state.turn += 1

            if state.turn % SUMMARY_EVERY == 0:
                state.rolling_summary = self.agent.summarize_history(
                    state.rolling_summary, '\n'.join(recent_history),
                )
                recent_history = []
                logger.info(f'  滚动摘要已更新（第{state.turn}回合）')

            if change.game_over:
                print('（故事已到达终点）')
                break

        final_fname = path.join(self.output_dir, 'final_state.json')
        write_text(final_fname, json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2))
        logger.info(f'💾 最终状态已保存：{final_fname}')
        return state

    # ── 主流程 ──────────────────────────────────────────────

    def run(self) -> None:
        novel_text = self.step_load_novel()
        assets = self.step_extract_assets(novel_text)
        self.step_save_assets(assets)
        if getattr(self.args, 'extract_only', False):
            logger.info('⏭ --extract-only，停止于资产抽取')
            return
        state = self.step_init_state(assets)
        self.step_run_game(state, assets)
        logger.info('[*] comic 已完成')


def comic(args):
    """CLI 入口函数：创建编排器并运行。"""
    orchestrator = ComicOrchestrator(args)
    orchestrator.run()


def reg_subparser(subparsers):
    parser = subparsers.add_parser(
        "comic",
        help="小说转文字游戏：离线抽取世界书/角色卡，再进入状态化对话式运行时",
    )
    parser.add_argument("novel", help="小说文本文件路径（UTF-8）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出目录（默认 <小说所在目录>/<书名>_game）")
    parser.add_argument("--extract-only", action="store_true",
                        help="仅执行离线资产抽取，不进入游戏运行时")
    parser.set_defaults(func=comic)
