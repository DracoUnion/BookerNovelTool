# -*- coding: utf-8 -*-
"""gal-play 子命令：加载资产包，进入状态化交互式文字游戏运行时。"""

import json
import logging
import os
from os import path
from typing import List, Optional, Iterator

from .gal_agent import GalAgent
from .gal_engine import GameEngine
from .gal_models import AssetsBundle, GameState, SaveFile, TurnResult
from .util import read_text, write_text

logger = logging.getLogger(__name__)

_DEFAULT_SAVE_NAME = 'save.json'


class GalPlayOrchestrator:
    """gal-play 编排器：加载资产包与存档 → 交互回合循环 → 命令行/脚本回放。"""

    def __init__(self, args):
        self.args = args
        self.agent = GalAgent(args)
        self.assets_dir = args.assets_dir
        self.save_path = args.save or path.join(self.assets_dir, _DEFAULT_SAVE_NAME)
        self.max_turns = getattr(args, 'max_turns', None)
        self.script_path = args.script
        self.log_path = args.log
        self.ui = getattr(args, 'ui', 'plain')

        self.assets: AssetsBundle = self._load_assets()
        self.manifest = self._load_manifest()
        self.history_window: List[str] = []
        state = self._load_save()
        self.engine = GameEngine(self.assets, state)

    # ── 资产与存档加载 ────────────────────────────────────

    def _load_assets(self) -> AssetsBundle:
        worldbook_fname = path.join(self.assets_dir, 'worldbook.json')
        scenes_fname = path.join(self.assets_dir, 'scenes.json')
        state_fname = path.join(self.assets_dir, 'initial_state.json')
        for fname in (worldbook_fname, scenes_fname, state_fname):
            if not path.isfile(fname):
                logger.fatal(f'资产包缺失：{fname}')
                raise FileNotFoundError(fname)
        from .gal_models import WorldBook, Scene

        worldbook = WorldBook(**json.loads(read_text(worldbook_fname)))
        scenes = [Scene(**s) for s in json.loads(read_text(scenes_fname))]
        initial_state = GameState(**json.loads(read_text(state_fname)))
        logger.info(
            f'📦 资产包已加载：{self.assets_dir} '
            f'(角色 {len(worldbook.characters)}，地点 {len(worldbook.locations)}，场景 {len(scenes)})'
        )
        return AssetsBundle(worldbook=worldbook, scenes=scenes, initial_state=initial_state)

    def _load_manifest(self) -> dict:
        text = read_text(path.join(self.assets_dir, 'manifest.json'))
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _load_save(self) -> GameState:
        """存在存档则读档并校验 assets_hash；否则使用初始状态。"""
        text = read_text(self.save_path)
        if not text:
            logger.info('▶ 无存档，使用资产包初始状态')
            return self.assets.initial_state
        try:
            save = SaveFile(**json.loads(text))
        except (json.JSONDecodeError, ValueError) as ex:
            logger.warning(f'存档损坏，忽略：{ex}')
            return self.assets.initial_state
        asset_hash = self.manifest.get('source_hash', '')
        if save.assets_hash and asset_hash and save.assets_hash != asset_hash:
            logger.fatal(
                f'存档资产包版本（{save.assets_hash}）与当前资产包（{asset_hash}）不一致，拒绝读档'
            )
            raise ValueError('存档与资产包版本不一致')
        self.history_window = list(save.history_window)
        logger.info(
            f'🔄 已读档：{self.save_path}（回合 {save.state.turn}，历史 {len(self.history_window)} 条）'
        )
        return save.state

    def _save(self) -> None:
        save = SaveFile(
            state=self.engine.state,
            history_window=self.history_window,
            assets_hash=self.manifest.get('source_hash', ''),
        )
        write_text(
            self.save_path,
            json.dumps(save.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        logger.info(f'💾 已存档：{self.save_path}（回合 {self.engine.state.turn}）')

    # ── 元命令 ───────────────────────────────────────────

    def _handle_meta(self, command: str) -> bool:
        """处理 / 开头的元命令；返回 False 表示退出游戏。"""
        cmd = command.strip().lower()
        if cmd in ('/quit', '/exit', '/q'):
            return False
        if cmd == '/save':
            self._save()
            print('已存档。')
            return True
        if cmd == '/load':
            self.history_window = []
            new_state = self._load_save()
            self.engine.state = new_state
            print('已读档。')
            return True
        if cmd == '/state':
            st = self.engine.state
            loc = self.engine.location_index.get(st.player_location)
            print(
                '=== 当前状态 ===\n'
                f'  位置：{st.player_location}' + (f'（{loc.name}）' if loc else '（未知）')
                + f'\n  背包：{", ".join(st.inventory) or "空"}'
                + f'\n  标志：{dict(st.flags)}'
                + f'\n  关系：{ {k: round(v, 2) for k, v in st.relationships.items()} }'
                + f'\n  在场：{", ".join(st.present_characters) or "无"}'
                + f'\n  回合：{st.turn}  已结束：{st.game_over}'
                + f'\n  滚动摘要：{st.rolling_summary or "（空）"}'
                + f'\n  历史窗口：{len(self.history_window)} 条'
            )
            return True
        if cmd == '/help':
            print(
                '可用命令：\n'
                '  直接输入行动/对话，回车推进一回合；\n'
                '  /save 存档   /load 读档   /state 查看状态   /help 帮助   /quit 退出'
            )
            return True
        print(f'未知命令：{command}，输入 /help 查看帮助。')
        return True

    # ── 渲染 ─────────────────────────────────────────────

    @staticmethod
    def _speaker_name(engine: GameEngine, speaker_id: Optional[str]) -> str:
        if not speaker_id:
            return '旁白'
        ch = engine.char_index.get(speaker_id)
        return ch.name if ch else speaker_id

    def _render_turn(self, turn_result: TurnResult) -> None:
        print('\n' + turn_result.narration)
        for d in turn_result.dialogue or []:
            speaker = self._speaker_name(self.engine, d.get('speaker_id'))
            print(f'  {speaker}：{d.get("line", "")}' + (f' [{d.get("emotion")}]' if d.get('emotion') else ''))
        if turn_result.scene_change:
            loc = self.engine.location_index.get(turn_result.scene_change)
            print(f'[场景转移 → {turn_result.scene_change}' + (f'：{loc.name}' if loc else '') + ']')
        if turn_result.flag_update:
            print(f'[标志更新：{turn_result.flag_update}]')
        print()

    # ── 回合循环 ─────────────────────────────────────────

    def _script_inputs(self) -> Optional[Iterator[str]]:
        if not self.script_path:
            return None
        with open(self.script_path, encoding='utf8') as f:
            return iter([line.rstrip('\n') for line in f if line.strip()])

    def step_run_game(self) -> None:
        logger.info('🎮 进入游戏运行时（输入 /help 查看命令，/quit 退出）')
        inputs = self._script_inputs()
        log_fh = None
        if self.log_path:
            log_fh = open(self.log_path, 'a', encoding='utf8')

        turn = 0
        try:
            while True:
                if self.engine.state.game_over:
                    print('（故事已到达终点）')
                    break
                if self.max_turns is not None and turn >= self.max_turns:
                    print(f'（已达 --max-turns {self.max_turns}，退出）')
                    break

                if inputs is not None:
                    try:
                        player_input = next(inputs)
                    except StopIteration:
                        break
                    print(f'> {player_input}')
                else:
                    try:
                        player_input = input('> ').strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                if not player_input:
                    continue
                if player_input.startswith('/'):
                    if not self._handle_meta(player_input):
                        print('游戏结束。')
                        break
                    continue

                turn += 1
                context = self.engine.assemble_context(player_input)
                recent = self.engine.recent_history_text(self.history_window)

                turn_result = self.agent.director_turn(
                    context['worldbook'],
                    context['state'],
                    context['rolling_summary'],
                    recent,
                    player_input,
                )
                ok, warnings = self.engine.apply(turn_result)
                if not ok:
                    feedback = (
                        '上一回合输出含非法世界变更：'
                        + '; '.join(warnings)
                        + ' 请仅修正非法字段，重新输出一个合法的 TurnResult JSON。'
                    )
                    turn_result = self.agent.director_turn(
                        context['worldbook'],
                        context['state'],
                        context['rolling_summary'],
                        recent,
                        player_input,
                        validation_feedback=feedback,
                    )
                    ok, warnings = self.engine.apply(turn_result)
                    if not ok:
                        turn_result = TurnResult(
                            narration=(turn_result.narration or '（本回合世界未发生合法变更）'),
                            game_over=False,
                        )
                        logger.warning('TurnResult 多次校验失败，已降级为仅叙事，不改变状态')

                self.history_window.append(f'玩家：{player_input}')
                self.history_window.append(f'世界：{turn_result.narration}')
                self.history_window = self.engine.fold_history_if_needed(
                    self.history_window, player_input, self.agent.summarize_history
                )

                self._render_turn(turn_result)

                if log_fh:
                    log_fh.write(
                        json.dumps(turn_result.model_dump(mode="json"), ensure_ascii=False) + '\n'
                    )
                    log_fh.flush()

                if turn_result.game_over or self.engine.state.game_over:
                    print('（故事已到达终点）')
                    break
        finally:
            if log_fh:
                log_fh.close()
            self._save()
            logger.info('[*] gal-play 已完成')


def gal_play(args):
    """CLI 入口函数：创建编排器并运行。"""
    GalPlayOrchestrator(args).step_run_game()


def reg_subparser(subparsers):
    parser = subparsers.add_parser(
        "gal-play",
        help="加载资产包，进入状态化交互式文字游戏运行时",
    )
    parser.add_argument("assets_dir", help="gal-parse 产出的资产包目录")
    parser.add_argument("-s", "--save", default=None, help="存档路径（不存在则新建；存在则读档继续）")
    parser.add_argument(
        "--ui", choices=['plain', 'rich'], default='plain', help="界面模式，默认 plain"
    )
    parser.add_argument(
        "--max-turns", type=int, default=None, help="自动跑 N 轮后退出（用于测试）"
    )
    parser.add_argument(
        "--script", default=None, help="脚本模式：逐行读取玩家输入（测试/回放用）"
    )
    parser.add_argument(
        "--log", default=None, help="将每轮 TurnResult 追加写入 JSONL"
    )
    parser.set_defaults(func=gal_play)
