# -*- coding: utf-8 -*-
"""Integration test: mock LLM calls, exercise orchestrators end-to-end."""
import os
import tempfile
from argparse import Namespace

from BookerNovelTool.write_novel import WriteNovelOrchestrator
from BookerNovelTool.write_novel_models import (
    ConceptPlanningResult, OpeningPlanResult, VolumeOutlineResult,
    VolumeOutlineItem, ChapterOutlineItem, CharacterState,
    ConsistencyReviewResult,
)
from BookerNovelTool.gts_fiction import GtsFictionOrchestrator

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

if __name__ == '__main__':
    test_write_novel()
    test_gts_fiction()
    print('ALL INTEGRATION TESTS PASSED')
