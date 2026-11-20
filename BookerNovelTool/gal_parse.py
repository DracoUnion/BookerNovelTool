# -*- coding: utf-8 -*-
"""gal-parse 子命令：小说 → 游戏资产包（worldbook / scenes / 初始状态）。"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from os import path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .gal_agent import GalAgent
from .gal_models import AssetsBundle, GameState
from .novel_anls import extract_text_from_epub
from .novel_anls_models import Chapter
from .util import md5, read_text, write_text

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r'^\s*(第\s*[^\n]{1,40}?章)\s*$')


def _split_text_into_chapters(text: str) -> List[Chapter]:
    """纯文本按“第…章”行标题切分；全文无标题时视为单章。"""
    chapters: List[Chapter] = []
    current_title: Optional[str] = None
    current_lines: List[str] = []
    index = 0

    def flush() -> None:
        nonlocal current_title, current_lines, index
        if current_title is None and not current_lines:
            return
        index += 1
        content = '\n'.join(current_lines).strip()
        if content:
            chapters.append(
                Chapter(
                    index=index,
                    title=current_title or f'第{index}章',
                    text=content,
                )
            )
        current_title = None
        current_lines = []

    for line in text.split('\n'):
        m = _HEADING_RE.match(line)
        if m:
            flush()
            current_title = m.group(1).strip()
        else:
            current_lines.append(line)
    flush()
    if not chapters:
        chapters.append(Chapter(index=1, title='第1章', text=text.strip()))
    return chapters


def _parse_range(rng: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """解析章节范围，如 '1-5'；None 或空表示全部。"""
    if not rng:
        return None, None
    rng = rng.strip()
    m = re.match(r'(\d+)\s*-\s*(\d+)$', rng)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r'^(\d+)$', rng)
    if m:
        n = int(m.group(1))
        return n, n
    return None, None


class GalParseOrchestrator:
    """gal-parse 编排器：加载小说 → 分章抽取（并发） → 实体合并 → 保存资产包。"""

    def __init__(self, args):
        self.args = args
        self.agent = GalAgent(args)
        self.input_path = args.input
        self.output_dir = args.out
        self.max_chars = int(getattr(args, 'max_chars', 12000))
        self.concurrency = int(getattr(args, 'concurrency', 4))
        self.skip_existing = bool(getattr(args, 'skip_existing', False))
        self.no_merge = bool(getattr(args, 'no_merge', False))
        os.makedirs(self.output_dir, exist_ok=True)

    # ── 步骤 1：加载小说 ──────────────────────────────────

    def step_load_source(self) -> List[Chapter]:
        logger.info(f'📖 加载小说：{self.input_path}')
        if self.input_path.lower().endswith('.epub'):
            chapters = extract_text_from_epub(self.input_path)
        else:
            text = read_text(self.input_path)
            if not text:
                logger.fatal(f'小说文件不存在或为空：{self.input_path}')
                raise FileNotFoundError(self.input_path)
            chapters = _split_text_into_chapters(text)

        start, end = _parse_range(getattr(self.args, 'chapters', None))
        if start is not None:
            chapters = [c for c in chapters if start <= c.index <= end]
            logger.info(f'  章节范围过滤：{start}-{end}，剩余 {len(chapters)} 章')

        for c in chapters:
            if len(c.text) > self.max_chars:
                c.text = c.text[: self.max_chars]
                logger.info(f'  第{c.index}章已截断至 {self.max_chars} 字')

        logger.info(f'✅ 共 {len(chapters)} 章')
        return chapters

    # ── 步骤 2：分章抽取（并发，YAML 文件缓存）─────────────

    def _extract_one(self, chapter: Chapter) -> dict:
        characters = self.agent.extract_characters(chapter.text, chapter.index)
        scenes = self.agent.extract_scenes(chapter.text, chapter.index)
        locations = self.agent.extract_locations(chapter.text, chapter.index)
        logger.info(
            f'  第{chapter.index}章：角色 {len(characters)}，场景 {len(scenes)}，地点 {len(locations)}'
        )
        return {
            'chapter': chapter,
            'characters': characters,
            'scenes': scenes,
            'locations': locations,
        }

    def step_extract_all(self, chapters: List[Chapter]) -> List[dict]:
        results: List[dict] = []
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = [executor.submit(self._extract_one, c) for c in chapters]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda r: r['chapter'].index)
        return results

    # ── 步骤 3：跨章实体合并 ──────────────────────────────

    def step_merge_entities(
        self,
        full_text: str,
        per_chapter: List[dict],
    ):
        if self.no_merge:
            logger.info('⏭ --no-merge：跳过实体合并')
            characters = [ch for p in per_chapter for ch in p['characters']]
            locations = [loc for p in per_chapter for loc in p['locations']]
            # 简单去重：同 id 保留第一个
            seen_c, seen_l = set(), set()
            characters = [c for c in characters if not (c.id in seen_c or seen_c.add(c.id))]
            locations = [l for l in locations if not (l.id in seen_l or seen_l.add(l.id))]
            from .gal_models import WorldBook
            return WorldBook(
                title=getattr(self.args, 'book_title', None) or path.splitext(
                    path.basename(self.input_path)
                )[0],
                source_hash=md5(full_text),
                characters=characters,
                locations=locations,
            )
        logger.info('🧩 跨章实体合并去重')
        return self.agent.merge_entities(
            full_text,
            [p['characters'] for p in per_chapter],
            [p['locations'] for p in per_chapter],
        )

    # ── 步骤 4：构建初始状态 ──────────────────────────────

    @staticmethod
    def _build_initial_state(worldbook, scenes) -> GameState:
        first_loc_id = worldbook.locations[0].id if worldbook.locations else ''
        present: List[str] = []
        if scenes:
            present = list(scenes[0].characters_present)
        if not present:
            present = [ch.id for ch in worldbook.characters if ch.role == 'protagonist']
        return GameState(
            player_location=first_loc_id,
            inventory=[],
            flags={},
            relationships={},
            turn=0,
            rolling_summary='',
            present_characters=present,
            game_over=False,
        )

    # ── 步骤 5：保存资产包 ────────────────────────────────

    def step_save_assets(self, bundle: AssetsBundle) -> None:
        worldbook_fname = path.join(self.output_dir, 'worldbook.json')
        scenes_fname = path.join(self.output_dir, 'scenes.json')
        state_fname = path.join(self.output_dir, 'initial_state.json')
        write_text(
            worldbook_fname,
            json.dumps(bundle.worldbook.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        write_text(
            scenes_fname,
            json.dumps([s.model_dump(mode="json") for s in bundle.scenes], ensure_ascii=False, indent=2),
        )
        write_text(
            state_fname,
            json.dumps(bundle.initial_state.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        manifest = {
            'source_hash': bundle.worldbook.source_hash,
            'model': getattr(self.args, 'model', None),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'input': self.input_path,
            'chapters': len(bundle.scenes) and len({s.chapter for s in bundle.scenes}),
            'characters': len(bundle.worldbook.characters),
            'locations': len(bundle.worldbook.locations),
            'scenes': len(bundle.scenes),
        }
        write_text(
            path.join(self.output_dir, 'manifest.json'),
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        logger.info(
            f'💾 资产包已保存：{self.output_dir} '
            f'(角色 {manifest["characters"]}，地点 {manifest["locations"]}，场景 {manifest["scenes"]})'
        )

    def _source_hash(self, chapters: List[Chapter]) -> str:
        return md5('\n\n'.join(c.text for c in chapters))

    def _skip_if_cached(self, source_hash: str) -> bool:
        manifest_text = read_text(path.join(self.output_dir, 'manifest.json'))
        if not manifest_text:
            return False
        try:
            data = json.loads(manifest_text)
        except json.JSONDecodeError:
            return False
        if data.get('source_hash') == source_hash:
            logger.info('⏭ skip-existing：source_hash 命中，跳过解析（缓存命中）')
            return True
        return False

    # ── 主流程 ─────────────────────────────────────────────

    def run(self) -> None:
        chapters = self.step_load_source()
        if not chapters:
            logger.fatal('未解析出任何章节')
            return

        source_hash = self._source_hash(chapters)
        if self.skip_existing and self._skip_if_cached(source_hash):
            return

        full_text = '\n\n'.join(c.text for c in chapters)
        per_chapter = self.step_extract_all(chapters)

        worldbook = self.step_merge_entities(full_text, per_chapter)
        # 由编排器统一掌舵 source_hash（缓存失效与存档版本校验的依据）
        worldbook.source_hash = source_hash

        scenes = []
        for i, (s, chap_idx) in enumerate(
            [(s, p['chapter'].index) for p in per_chapter for s in p['scenes']], 1
        ):
            s.scene_number = i
            s.chapter = chap_idx
            scenes.append(s)

        initial_state = self._build_initial_state(worldbook, scenes)
        bundle = AssetsBundle(
            worldbook=worldbook,
            scenes=scenes,
            initial_state=initial_state,
        )
        self.step_save_assets(bundle)
        logger.info('[*] gal-parse 已完成')


def gal_parse(args):
    """CLI 入口函数：创建编排器并运行。"""
    GalParseOrchestrator(args).run()


def reg_subparser(subparsers):
    parser = subparsers.add_parser(
        "gal-parse",
        help="小说离线解构：EPUB/纯文本 → 世界书/场景/初始状态资产包",
    )
    parser.add_argument("input", help="小说文件路径（EPUB 或 UTF-8 纯文本）")
    parser.add_argument("-o", "--out", required=True, help="资产包输出目录")
    parser.add_argument(
        "-c", "--chapters", default=None, help="章节范围，如 1-5；默认全部"
    )
    parser.add_argument(
        "--max-chars", type=int, default=12000, help="单章截断长度，默认 12000"
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="资产包已存在且 source_hash 命中则跳过",
    )
    parser.add_argument(
        "--concurrency", type=int, default=4, help="章节并发解析数，默认 4"
    )
    parser.add_argument(
        "--no-merge", action="store_true", help="跳过跨章实体合并（调试用）"
    )
    parser.set_defaults(func=gal_parse)
