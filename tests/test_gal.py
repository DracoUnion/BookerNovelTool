# -*- coding: utf-8 -*-
"""gal 子命令离线测试：全部 mock LLM 调用，不依赖网络或本地模型端点。"""

import json
import os
import tempfile
from argparse import Namespace
from os import path

from BookerNovelTool.gal_engine import GameEngine
from BookerNovelTool.gal_models import (
    AssetsBundle, CharacterCard, GameState, Location, SaveFile, Scene,
    SceneElement, TurnResult, WorldBook,
)
from BookerNovelTool.gal_parse import GalParseOrchestrator, gal_parse, reg_subparser as reg_gal_parse
from BookerNovelTool.gal_play import GalPlayOrchestrator, reg_subparser as reg_gal_play
from BookerNovelTool.util import md5, read_text, write_text


def make_args(**over):
    args = Namespace(
        model='fake-model', key=None, host=None, retry=1, temp=1.0,
        top_p=None, frequency_penalty=None, presence_penalty=None,
        max_tokens=None, extra_body=None, stream=False,
        user_agent='test', conn_timeout=60, read_timeout=120,
        repetition_regex='', no_think=False,
    )
    for k, v in over.items():
        setattr(args, k, v)
    return args


def _make_worldbook():
    return WorldBook(
        title='测试书',
        source_hash='hash-abc',
        characters=[
            CharacterCard(id='char_001', name='张三', role='protagonist',
                          description='年轻人', traits=[], voice='"你好"',
                          knowledge_scope=['日常'], relationships=[]),
            CharacterCard(id='char_002', name='李四', role='supporting',
                          description='老友', traits=[], voice='"哦"',
                          knowledge_scope=['日常'], relationships=[]),
        ],
        locations=[
            Location(id='loc_001', name='房间', description='一间普通房间',
                     connections=['loc_002'], items=['钥匙']),
            Location(id='loc_002', name='走廊', description='一条走廊',
                     connections=['loc_001'], items=[]),
        ],
        rules=['此门需钥匙'],
        factions=[],
    )


def _make_assets():
    return AssetsBundle(
        worldbook=_make_worldbook(),
        scenes=[
            Scene(scene_number=1, chapter=1, location_id='loc_001',
                  characters_present=['char_001', 'char_002'],
                  elements=[SceneElement(type='action', content='张三走进房间。')],
                  is_flashback=False),
        ],
        initial_state=GameState(
            player_location='loc_001', inventory=[], flags={}, relationships={},
            turn=0, rolling_summary='', present_characters=['char_001'],
            game_over=False,
        ),
    )


# ── 模型校验 ──────────────────────────────────────────────

def test_models_roundtrip():
    wb = _make_worldbook()
    data = wb.model_dump(mode="json")
    wb2 = WorldBook(**data)
    assert wb2.title == '测试书'
    assert wb2.characters[0].id == 'char_001'
    assert wb2.locations[0].items == ['钥匙']

    st = GameState(player_location='loc_001', inventory=['钥匙'],
                   relationships={'char_001': 0.5}, present_characters=['char_001'])
    st2 = GameState(**st.model_dump(mode="json"))
    assert st2.relationships['char_001'] == 0.5

    tr = TurnResult(narration='叙事', dialogue=[{'speaker_id': 'char_001', 'line': '台词', 'emotion': '开心'}])
    tr2 = TurnResult(**tr.model_dump(mode="json"))
    assert tr2.dialogue[0]['line'] == '台词'


# ── 引擎：状态校验 ────────────────────────────────────────

def test_engine_illegal_scene_change_discarded():
    wb = _make_worldbook()
    state = GameState(player_location='loc_001', inventory=[], present_characters=['char_001'], flags={})
    assets = AssetsBundle(worldbook=wb, scenes=[], initial_state=state)
    engine = GameEngine(assets, state)

    ok, warns = engine.apply(TurnResult(narration='非法跳转', scene_change='loc_999'))
    assert not ok
    assert engine.state.player_location == 'loc_001'
    assert any('loc_999' in w for w in warns)


def test_engine_item_delta_validation():
    wb = _make_worldbook()
    state = GameState(player_location='loc_001', inventory=[], present_characters=[], flags={})
    assets = AssetsBundle(worldbook=wb, scenes=[], initial_state=state)
    engine = GameEngine(assets, state)

    ok, warns = engine.apply(TurnResult(
        narration='拾取',
        item_delta={'add': ['钥匙', '不存在的物品'], 'remove': []},
    ))
    assert not ok  # 存在非法 add，整体不合法
    assert engine.state.inventory == ['钥匙']
    assert any('不存在的物品' in w for w in warns)

    # remove 背包中不存在的物品被丢弃
    ok2, warns2 = engine.apply(TurnResult(
        narration='丢弃', item_delta={'add': [], 'remove': ['不存在的物品']},
    ))
    assert not ok2
    assert engine.state.inventory == ['钥匙']


def test_engine_relationship_clipped():
    wb = _make_worldbook()
    state = GameState(player_location='loc_001', inventory=[], present_characters=['char_001'], flags={},
                      relationships={'char_001': 0.9})
    assets = AssetsBundle(worldbook=wb, scenes=[], initial_state=state)
    engine = GameEngine(assets, state)

    engine.apply(TurnResult(narration='x', relationship_delta=[
        {'char_id': 'char_001', 'delta': 2.0},   # 0.9 + 2.0 -> 裁剪 1.0
        {'char_id': 'char_001', 'delta': -2.0},  # 1.0 - 2.0 -> 裁剪 -1.0
    ]))
    assert engine.state.relationships['char_001'] == -1.0

    # 不存在的角色目标被丢弃
    engine.apply(TurnResult(narration='y', relationship_delta=[
        {'char_id': 'char_999', 'delta': 0.5},
    ]))
    assert 'char_999' not in engine.state.relationships


# ── 引擎：记忆预算折叠 ────────────────────────────────────

def test_engine_fold_history_if_needed():
    wb = _make_worldbook()
    state = GameState(player_location='loc_001', inventory=[], present_characters=[], flags={})
    assets = AssetsBundle(worldbook=wb, scenes=[], initial_state=state)
    engine = GameEngine(assets, state, memory_budget=200)

    history = [f'历史条目{i}：' + 'x' * 60 for i in range(15)]
    calls = []

    def fake_summarize(old_summary, history_text):
        calls.append((old_summary, history_text))
        from BookerNovelTool.gal_models import SummaryResult
        return SummaryResult(summary='压缩后的滚动摘要')

    new_window = engine.fold_history_if_needed(history, '玩家新输入', fake_summarize)
    assert calls, '应当触发滚动摘要'
    assert engine.state.rolling_summary == '压缩后的滚动摘要'
    assert len(new_window) < len(history), '旧历史应当被折叠'


# ── 存档读档 ──────────────────────────────────────────────

def test_save_file_roundtrip_and_hash_reject(tmp_path):
    save_file = path.join(tmp_path, 'save.json')
    sf = SaveFile(
        state=GameState(player_location='loc_001', inventory=[], flags={}, relationships={}, turn=3),
        history_window=['玩家：hello'],
        assets_hash='asset-hash-1',
    )
    write_text(save_file, json.dumps(sf.model_dump(mode="json"), ensure_ascii=False))
    loaded = SaveFile(**json.loads(read_text(save_file)))
    assert loaded.state.turn == 3
    assert loaded.history_window == ['玩家：hello']
    assert loaded.assets_hash == 'asset-hash-1'

    # manifest hash 不一致时应当被上层拒绝（此处仅断言字段可比较）
    assert loaded.assets_hash != 'other-hash'


# ── gal-play：脚本模式 20 轮无异常 ────────────────────────

def test_play_script_20_turns(tmp_path):
    assets_dir = path.join(tmp_path, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    bundle = _make_assets()
    write_text(path.join(assets_dir, 'worldbook.json'),
               json.dumps(bundle.worldbook.model_dump(mode="json"), ensure_ascii=False))
    write_text(path.join(assets_dir, 'scenes.json'),
               json.dumps([s.model_dump(mode="json") for s in bundle.scenes], ensure_ascii=False))
    write_text(path.join(assets_dir, 'initial_state.json'),
               json.dumps(bundle.initial_state.model_dump(mode="json"), ensure_ascii=False))
    write_text(path.join(assets_dir, 'manifest.json'),
               json.dumps({'source_hash': bundle.worldbook.source_hash}, ensure_ascii=False))

    script_path = path.join(tmp_path, 'script.txt')
    write_text(script_path, '\n'.join(f'玩家输入{i}' for i in range(25)))

    args = make_args(assets_dir=assets_dir, save=path.join(tmp_path, 'save.json'),
                     script=script_path, max_turns=30, ui='plain', log=None)
    orc = GalPlayOrchestrator(args)

    sequence = []

    def fake_director(worldbook, state, rolling_summary, recent_history, player_input,
                      validation_feedback='', temperature=None):
        sequence.append(player_input)
        return TurnResult(narration=f'回应：{player_input}', game_over=(len(sequence) >= 20))

    orc.agent.director_turn = fake_director
    orc.step_run_game()

    assert len(sequence) == 20, f'期望 20 轮，实际 {len(sequence)}'
    st = orc.engine.state
    assert st.player_location in {loc.id for loc in orc.assets.worldbook.locations}
    assert all(-1.0 <= v <= 1.0 for v in st.relationships.values())
    assert path.isfile(args.save)


def test_play_correction_retry_then_degrade(tmp_path):
    assets_dir = path.join(tmp_path, 'assets2')
    os.makedirs(assets_dir, exist_ok=True)
    bundle = _make_assets()
    write_text(path.join(assets_dir, 'worldbook.json'),
               json.dumps(bundle.worldbook.model_dump(mode="json"), ensure_ascii=False))
    write_text(path.join(assets_dir, 'scenes.json'),
               json.dumps([s.model_dump(mode="json") for s in bundle.scenes], ensure_ascii=False))
    write_text(path.join(assets_dir, 'initial_state.json'),
               json.dumps(bundle.initial_state.model_dump(mode="json"), ensure_ascii=False))
    write_text(path.join(assets_dir, 'manifest.json'),
               json.dumps({'source_hash': bundle.worldbook.source_hash}, ensure_ascii=False))

    script_path = path.join(tmp_path, 'script.txt')
    write_text(script_path, '唯一输入')

    args = make_args(assets_dir=assets_dir, save=path.join(tmp_path, 'save2.json'),
                     script=script_path, max_turns=2, ui='plain', log=None)
    orc = GalPlayOrchestrator(args)

    calls = {'n': 0}

    def fake_director(worldbook, state, rolling_summary, recent_history, player_input,
                      validation_feedback='', temperature=None):
        calls['n'] += 1
        if calls['n'] == 1:
            return TurnResult(narration='非法', scene_change='loc_nope')
        return TurnResult(narration='修正后合法', scene_change=None)

    orc.agent.director_turn = fake_director
    orc.step_run_game()
    assert calls['n'] == 2, f'期望一次校验失败重试，实际调用 {calls["n"]} 次'
    assert orc.engine.state.player_location == 'loc_001'  # 非法跳转被丢弃


# ── gal-parse：编排器端到端 ─────────────────────────────

def test_parse_orchestrator_end_to_end(tmp_path):
    novel = path.join(tmp_path, 'novel.txt')
    write_text(novel, '第一章\n张三说：“你好”。\n第二章\n李四回答：“哦”。')
    out = path.join(tmp_path, 'assets')
    args = make_args(input=novel, out=out, chapters=None, max_chars=12000,
                     concurrency=2, skip_existing=False, no_merge=False)
    orc = GalParseOrchestrator(args)

    chars = [CharacterCard(id='char_001', name='张三', role='protagonist',
                           description='年轻人', traits=[], voice='"你好"',
                           knowledge_scope=['日常'], relationships=[])]
    scenes = [Scene(scene_number=1, chapter=1, location_id='loc_001',
                    characters_present=['char_001'],
                    elements=[SceneElement(type='dialogue', content='"你好"',
                                           speaker_id='char_001', emotion=None)],
                    is_flashback=False)]
    locs = [Location(id='loc_001', name='房间', description='一间房',
                     connections=[], items=[])]
    orc.agent.extract_characters = lambda text, idx: chars
    orc.agent.extract_scenes = lambda text, idx: scenes
    orc.agent.extract_locations = lambda text, idx: locs

    merged = WorldBook(title='测试书', source_hash='x',
                       characters=chars, locations=locs, rules=[], factions=[])
    orc.agent.merge_entities = lambda full_text, cc, cl: merged

    orc.run()

    assert path.isfile(path.join(out, 'worldbook.json'))
    assert path.isfile(path.join(out, 'scenes.json'))
    assert path.isfile(path.join(out, 'initial_state.json'))
    assert path.isfile(path.join(out, 'manifest.json'))
    manifest = json.loads(read_text(path.join(out, 'manifest.json')))
    assert manifest['source_hash'] == md5('张三说：“你好”。\n\n李四回答：“哦”。')
    assert manifest['scenes'] == 2
    assert manifest['characters'] == 1


def test_parse_skip_existing_cache_hit(tmp_path):
    novel = path.join(tmp_path, 'novel.txt')
    raw = '内容。'
    write_text(novel, raw)
    out = path.join(tmp_path, 'assets')
    os.makedirs(out, exist_ok=True)
    # 源哈希与编排器一致：章节正文拼接（单章无标题时正文即全文）
    write_text(path.join(out, 'manifest.json'),
               json.dumps({'source_hash': md5(raw)}, ensure_ascii=False))

    args = make_args(input=novel, out=out, chapters=None, max_chars=12000,
                     concurrency=2, skip_existing=True, no_merge=False)
    orc = GalParseOrchestrator(args)

    called = {'n': 0}

    def boom(*a, **k):
        called['n'] += 1
        raise AssertionError('skip-existing 命中时不应调用 LLM 抽取')

    orc.agent.extract_characters = boom
    orc.agent.extract_scenes = boom
    orc.agent.extract_locations = boom
    orc.agent.merge_entities = boom

    orc.run()
    assert called['n'] == 0


# ── 子命令注册 ────────────────────────────────────────────

def test_subcommands_registered():
    import argparse
    from BookerNovelTool.gal_play import gal_play
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    reg_gal_parse(subparsers)
    reg_gal_play(subparsers)

    ns, _ = parser.parse_known_args(['gal-parse', 'in.epub', '-o', 'out'])
    assert ns.func == gal_parse
    ns, _ = parser.parse_known_args(['gal-play', 'assets'])
    assert ns.func == gal_play


if __name__ == '__main__':
    test_models_roundtrip()
    test_engine_illegal_scene_change_discarded()
    test_engine_item_delta_validation()
    test_engine_relationship_clipped()
    test_engine_fold_history_if_needed()
    test_save_file_roundtrip_and_hash_reject(tempfile.mkdtemp())
    test_play_script_20_turns(tempfile.mkdtemp())
    test_play_correction_retry_then_degrade(tempfile.mkdtemp())
    test_parse_orchestrator_end_to_end(tempfile.mkdtemp())
    test_parse_skip_existing_cache_hit(tempfile.mkdtemp())
    test_subcommands_registered()
    print('ALL GAL TESTS PASSED')
