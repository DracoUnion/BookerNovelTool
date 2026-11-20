# -*- coding: utf-8 -*-
"""Integration test: mock LLM calls, exercise orchestrators end-to-end."""
import json
import os
import tempfile
from argparse import Namespace
from os import path

from BookerNovelTool.comic import ComicAgent, ComicOrchestrator
from BookerNovelTool.comic_models import (
    GameCharacter, GameItem, GameLocation, GameScene, GameState, InitialGameState,
    NovelGameAssets, SceneElement, Worldbook, WorldChange, ValidationResult,
)
from BookerNovelTool.gts_fiction import GtsFictionOrchestrator
from BookerNovelTool.util import write_text

from BookerNovelTool.write_novel import WriteNovelOrchestrator
from BookerNovelTool.write_novel_models import (
    ConceptPlanningResult, OpeningPlanResult, VolumeOutlineResult,
    VolumeOutlineItem, ChapterOutlineItem, CharacterState,
    ConsistencyReviewResult,
)

# ── 构造 args（保持与 __main__ 全局参数一致）────────────
def make_args(**over):
    args = Namespace(
        model='fake-model',
        key=None, host=None, retry=1, temp=1.0, top_p=None,
        frequency_penalty=None, presence_penalty=None,
        max_tokens=None, extra_body=None, stream=False,
        user_agent='test', conn_timeout=60, read_timeout=120,
        repetition_regex='', no_think=False,
    )
    for k, v in over.items():
        setattr(args, k, v)
    return args

# ── write-novel：mock 全部 LLM 调用，跑通完整流程 ─────────
def test_write_novel():
    work = tempfile.mkdtemp()
    args = make_args(out=os.path.join(work, 'novel'), chapters=3, check=2,
                     preview_len=50, debug=False, blurb='测试简介')

    orc = WriteNovelOrchestrator(args)
    orc.agent.gen_concept_planning = lambda blurb: ConceptPlanningResult(
        title='测试书', genre='玄幻', sub_genre='都市', main_consumption_points=['爽'],
        hook='hook', premise='premise', protagonist_goal='goal',
        main_conflict_source='conflict', story_engine='engine',
        target_length='短篇', length_reasoning='理由',
        volume_one_goal='v1goal', volume_one_ending_change='v1change',
        confidence_score=0.8, diagnosis_notes=[])
    orc.agent.gen_opening_plan = lambda concept: OpeningPlanResult(
        golden_three_chapters=['e1', 'e2', 'e3'], chapter_one_hook='hook1',
        chapter_one_selling_point='sp', chapter_one_protagonist_reveal='reveal',
        abnormal_situation='ab', first_6000_words_plan='plan')
    orc.agent.gen_volume_outline = lambda concept, opening_plan, chapter_count: \
        VolumeOutlineResult(
            golden_three_chapters_detail=['a', 'b', 'c'],
            volumes=[VolumeOutlineItem(no=1, title='卷1', goal='g',
                                       core_conflict='c', climax='cl', ending_change='ec')],
            chapter_outlines=[
                ChapterOutlineItem(no=i, title=f'第{i}章', core_event='e',
                                   protagonist_goal='g', obstacle='o',
                                   situation_change='s', hook_next='h')
                for i in range(1, chapter_count + 1)
            ])
    orc.agent.gen_opening_content = lambda concept, opening_plan: \
        '# 第1章\n开头正文一。\n\n# 第2章\n开头正文二。\n\n# 第3章\n开头正文三。'
    orc.agent.gen_chapter_body = lambda *a, **k: '模型生成的正文。'
    orc.agent.gen_character_state = lambda *a, **k: CharacterState(
        chapter_no=1, goal='g', emotion='e', key_relationships={},
        physical_state='p', knowledge_state='k', voice_style='v')
    orc.agent.check_consistency = lambda *a, **k: ConsistencyReviewResult(
        chapter_no=1, plot_logic_ok=True, character_goal_ok=True,
        emotion_relationship_ok=True, physical_info_ok=True,
        scene_transition_ok=True, chapter_end_hook_ok=True,
        overall_pass=True, issues=[])
    orc.agent.fix_chapter_body = lambda *a, **k: '修复后正文。'

    orc.run()

    # chapter_count=3 → 文件宽 1：article_1.md / article_2.md / article_3.md
    for i in range(1, 4):
        f = os.path.join(args.out, f'article_{i}.md')
        assert os.path.isfile(f), f
    assert os.path.isfile(os.path.join(args.out, 'README.md'))
    assert os.path.isdir(os.path.join(args.out, 'asset'))
    print('write-novel OK; files:', sorted(os.listdir(args.out)))

# ── gts-fiction：mock 全部 LLM 调用，跑通完整流程 ─────────
def test_gts_fiction():
    args = make_args(idea='测试创意', out_dir=tempfile.mkdtemp(), chapters=2,
                     words=500, write_command='cmd', polish_command='pc',
                     style_example='')
    orc = GtsFictionOrchestrator(args)
    orc.agent.generate_setting = lambda idea, command: '世界观'
    orc.agent.generate_roles = lambda setting, command: '角色'
    orc.agent.generate_outline = lambda setting, roles, nchapters, command: '大纲'
    orc.agent.generate_detail = lambda setting, roles, outline, i, command: f'细纲{i}'
    orc.agent.generate_body = lambda setting, roles, detail, i, command, nword: f'正文{i}'
    orc.agent.polish_body = lambda body, command, style: f'润色：{body}'

    orc.run()

    for f in ['世界观.md', '角色.md', '大纲.md', '细纲1.md', '细纲2.md',
              '正文1.md', '正文2.md', '润色正文1.md', '润色正文2.md']:
        assert os.path.isfile(os.path.join(args.out_dir, f)), f
    assert '润色：' in open(os.path.join(args.out_dir, '润色正文1.md'), encoding='utf8').read()
    print('gts-fiction OK; files:', sorted(os.listdir(args.out_dir)))

# ── comic：mock LLM，跑通离线抽取 + 运行时一回合 ──────────


def _make_comic_assets() -> NovelGameAssets:
    return NovelGameAssets(
        worldbook=Worldbook(
            characters=[
                GameCharacter(id='char_001', name='张三', role='主角', description='年轻人',
                              traits=[], relationships=[]),
                GameCharacter(id='char_002', name='李四', role='配角', description='老友',
                              traits=[], relationships=[]),
            ],
            locations=[
                GameLocation(id='loc_001', name='房间', description='一间普通房间'),
            ],
            items=[
                GameItem(id='item_001', name='钥匙', description='一把旧钥匙', location='loc_001'),
            ],
            scenes=[
                GameScene(
                    scene_number=1, location='loc_001',
                    characters_present=['char_001', 'char_002'],
                    elements=[SceneElement(type='action', content='张三走进房间。')],
                ),
            ],
            rules=[],
        ),
        initial_state=InitialGameState(
            location='loc_001', inventory=[], present_characters=['char_001'], flags={},
        ),
    )


def test_comic():
    work = tempfile.mkdtemp()
    novel = path.join(work, 'novel.txt')
    write_text(novel, '张三走进房间，看到李四坐在桌前。“你来了，”李四说。')
    args = make_args(novel=novel, output=path.join(work, 'game'))

    orc = ComicOrchestrator(args)
    assets = _make_comic_assets()
    orc.agent.extract_assets = lambda novel_text: assets
    orc.agent.runtime_turn = lambda *a, **k: WorldChange(
        narration='李四抬头看向你，微微一笑。', game_over=True,
    )

    inputs = iter(['环顾四周', 'quit'])
    import builtins
    orig_input = builtins.input
    builtins.input = lambda prompt='': next(inputs)
    try:
        orc.run()
    finally:
        builtins.input = orig_input

    assert os.path.isfile(path.join(args.output, 'worldbook.json'))
    assert os.path.isfile(path.join(args.output, 'initial_state.json'))
    assert os.path.isfile(path.join(args.output, 'final_state.json'))
    print('comic OK; files:', sorted(os.listdir(args.output)))


def test_comic_extract_only():
    work = tempfile.mkdtemp()
    novel = path.join(work, 'novel.txt')
    write_text(novel, '张三走进房间。')
    args = make_args(novel=novel, output=path.join(work, 'game'), extract_only=True)

    orc = ComicOrchestrator(args)
    assets = _make_comic_assets()
    orc.agent.extract_assets = lambda novel_text: assets
    called = []

    def _should_not_be_called(*a, **k):
        called.append(True)
        raise AssertionError('extract-only 模式不应调用运行时')

    orc.agent.runtime_turn = _should_not_be_called
    orc.agent.summarize_history = _should_not_be_called

    orc.run()

    assert not called, 'extract-only 模式不应进入运行时循环'
    assert os.path.isfile(path.join(args.output, 'worldbook.json'))
    assert os.path.isfile(path.join(args.output, 'initial_state.json'))
    assert not os.path.isfile(path.join(args.output, 'final_state.json'))
    print('comic extract-only OK; files:', sorted(os.listdir(args.output)))


# ── comic：硬规则裁判 ──────────────────────────────────────


def test_comic_validate_change():
    worldbook = Worldbook(
        locations=[GameLocation(id='loc_001', name='房间', description='一间房间')],
        characters=[GameCharacter(id='char_001', name='张三', role='主角', description='',
                                  traits=[], relationships=[])],
        items=[GameItem(id='item_001', name='钥匙', description='', location='loc_001')],
        scenes=[], rules=[],
    )
    state = GameState(location='loc_001', inventory=['item_001'],
                      present_characters=['char_001'], flags={})
    illegal = '{"narration":"非法跳转","scene_change":"loc_999"}'
    legal = '{"narration":"合法留在原地","scene_change":null}'

    args = make_args(novel='/tmp/x.txt', output=tempfile.mkdtemp())
    agent = ComicAgent(args)
    calls = {'n': 0}

    def fake_llm(ques, model_name, args_, parse_output=None):
        calls['n'] += 1
        raw = illegal if calls['n'] == 1 else legal
        return parse_output(f'```json\n{raw}\n```')

    agent.llm.ask_chatgpt_retry = fake_llm
    vresults = iter([
        ValidationResult(valid=False, reason='scene_change loc_999 不存在',
                         fixes=['将 scene_change 改为 loc_001 或 null']),
        ValidationResult(valid=True),
    ])
    agent.validate_change = lambda wb, st, ch: next(vresults)

    change = agent.runtime_turn(worldbook, state, '', '', '测试输入')
    assert change.scene_change is None, change
    assert calls['n'] == 2, f'期望 LLM 被回填重写一次，实际调用 {calls["n"]} 次'
    print('comic validate_change OK')


# ── comic：--resume 可恢复运行时 ───────────────────────────


def test_comic_resume():
    work = tempfile.mkdtemp()
    out = path.join(work, 'game')
    os.makedirs(out, exist_ok=True)
    assets = _make_comic_assets()
    write_text(path.join(out, 'worldbook.json'),
               json.dumps(assets.worldbook.model_dump(mode="json"), ensure_ascii=False))
    write_text(path.join(out, 'initial_state.json'),
               json.dumps(assets.initial_state.model_dump(mode="json"), ensure_ascii=False))
    final_state = {
        "location": "loc_002", "inventory": ["item_001"],
        "present_characters": ["char_001"],
        "relationships": {"char_002": 0.5},
        "flags": {"met": True}, "rolling_summary": "已恢复测试", "turn": 7,
    }
    write_text(path.join(out, 'final_state.json'), json.dumps(final_state, ensure_ascii=False))
    args = make_args(novel=path.join(work, 'novel.txt'), output=out, resume=True)
    write_text(args.novel, 'x')
    orc = ComicOrchestrator(args)
    captured = {}
    orc.step_run_game = lambda s, a: (captured.update(state=s), s)
    orc.run()
    s = captured['state']
    assert s.location == 'loc_002', s
    assert s.turn == 7, s
    assert s.rolling_summary == '已恢复测试', s
    assert s.relationships.get('char_002') == 0.5, s
    print('comic resume OK')


# ── comic：--approve-worldbook 资产审批 ────────────────────


def test_comic_approve_worldbook_reject():
    work = tempfile.mkdtemp()
    novel = path.join(work, 'novel.txt')
    write_text(novel, '张三走进房间。')
    out = path.join(work, 'game')
    args = make_args(novel=novel, output=out, approve_worldbook=True)
    orc = ComicOrchestrator(args)
    assets = _make_comic_assets()
    orc.agent.extract_assets = lambda novel_text: assets
    called = []
    orc.step_run_game = lambda s, a: called.append(True)
    import builtins
    orig_input = builtins.input
    builtins.input = lambda prompt='': 'n'
    try:
        orc.run()
    finally:
        builtins.input = orig_input
    assert not called, 'approve-worldbook 拒绝后不应进入运行时'
    assert path.isfile(path.join(out, 'worldbook.json'))
    assert not path.isfile(path.join(out, 'final_state.json'))
    print('comic approve-worldbook reject OK')


def test_comic_approve_worldbook_accept():
    work = tempfile.mkdtemp()
    novel = path.join(work, 'novel.txt')
    write_text(novel, '张三走进房间。')
    out = path.join(work, 'game')
    args = make_args(novel=novel, output=out, approve_worldbook=True)
    orc = ComicOrchestrator(args)
    assets = _make_comic_assets()
    orc.agent.extract_assets = lambda novel_text: assets
    orc.agent.runtime_turn = lambda *a, **k: WorldChange(narration='结束', game_over=True)
    called = []
    orc.step_run_game = lambda s, a: called.append(True)
    import builtins
    orig_input = builtins.input
    builtins.input = lambda prompt='': 'y'
    try:
        orc.run()
    finally:
        builtins.input = orig_input
    assert called, 'approve-worldbook 确认后应进入运行时'
    print('comic approve-worldbook accept OK')


if __name__ == '__main__':
    test_write_novel()
    test_gts_fiction()
    test_comic()
    test_comic_extract_only()
    test_comic_validate_change()
    test_comic_resume()
    test_comic_approve_worldbook_reject()
    test_comic_approve_worldbook_accept()
    print('ALL INTEGRATION TESTS PASSED')
