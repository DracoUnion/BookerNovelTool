# -*- coding: utf-8 -*-
"""gal-parse 子命令：小说 → 游戏资产包（worldbook / scenes / 初始状态）。"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from os import path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .gal_agent import GalAgent
from .gal_models import AssetsBundle, GameState, WorldBook
from .novel_anls import extract_text_from_epub
from .novel_anls_models import Chapter
from .util import md5, read_text, write_text

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r'^\s*(第\s*[^\n]{1,40}?章)\s*$')
_MD_HEADING_RE = re.compile(r'^\s{0,3}#{1,6}\s+(.{1,60}?)\s*$')
_NUM_DOT_RE = re.compile(r'^\s*(\d{1,3}[.、](?![0-9０-９])\s{0,3}\S.{1,40})\s*$')
_BRACKET_NUM_RE = re.compile(
    r'^\s*(?:\[\(\d+\)\]|\[\d+\]|\(\d+\)|\[\d+\]|\[－\d+－\])\s+(.{1,40})\s*$'
)


def _detect_heading(line: str) -> Optional[str]:
    """按优先级识别章节标题行：第…章 > Markdown # > 数字点号 > 方括号编号。

    返回标题文本，非标题行返回 None。
    """
    m = _HEADING_RE.match(line)
    if m:
        return m.group(1).strip()
    m = _MD_HEADING_RE.match(line)
    if m:
        return m.group(1).strip()
    m = _NUM_DOT_RE.match(line)
    if m:
        return m.group(1).strip()
    m = _BRACKET_NUM_RE.match(line)
    if m:
        return m.group(1).strip()
    return None


def _split_text_into_chapters(text: str) -> List[Chapter]:
    """纯文本按章节标题切分；全文无标题时视为单章。

    支持的标题形态（按优先级）：
      1. 第…章（中文章节）
      2. # / ## Markdown 标题
      3. 1. / 13、 数字点号（数字≤3位，后不紧跟数字，标题≤40字）
      4. [(1)] / [1] 方括号编号
    """
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
        title = _detect_heading(line)
        if title is not None:
            flush()
            current_title = title
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

    # ── 相位标记（参考 comic.py _write_state_marker）──────────

    _STATE_MARKER_FILE = 'gal-state.json'

    def _write_state_marker(self, phase: str, detail: Optional[str] = None, turn: Optional[int] = None) -> None:
        marker = {
            'phase': phase,
            'detail': detail,
            'turn': turn,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        write_text(path.join(self.output_dir, self._STATE_MARKER_FILE),
                   json.dumps(marker, ensure_ascii=False, indent=2))

    def _read_state_marker(self) -> Optional[dict]:
        text = read_text(path.join(self.output_dir, self._STATE_MARKER_FILE))
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

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

    # ── 步骤 4：资产包验收（--validate，~13 项确定性检查）─────

    def step_validate_assets(self, bundle: AssetsBundle) -> bool:
        """对资产包做确定性验收，失败列出清单供人工修复。

        检查项：
          1. 场景数 ≥ 章节数 × 4（3000 字/章基准）
          2. 角色卡去重：同名角色仅出现一次
          3. 场景 location_id 必须存在于世界书
          4. 场景元素 type 必须合法
          5. 闪回场景不得为概括性单元素
          6. 场景在场角色 ID 必须存在于世界书
          7. initial_state.player_location 必须存在于世界书
          8. initial_state.present_characters 必须存在于世界书
          9. 初始背包物品必须存在于某地点 items
          10. worldbook.rules 非空（世界硬规则）
          11. manifest source_hash 与世界书一致
          12. 无空场景（elements 非空）
          13. 对话元素必须带 speaker_id
        """
        errors: List[str] = []
        wb = bundle.worldbook
        scenes = bundle.scenes
        st = bundle.initial_state

        loc_ids = {loc.id for loc in wb.locations}
        char_ids = {ch.id for ch in wb.characters}

        # 1. 场景完整性
        chapter_count = len({s.chapter for s in scenes}) or 1
        if len(scenes) < chapter_count * 4:
            errors.append(
                f'场景完整性不足：{len(scenes)} 个场景 < 章节数 {chapter_count} × 4'
            )

        # 2. 角色去重
        name_count: Dict[str, int] = {}
        for ch in wb.characters:
            name_count[ch.name] = name_count.get(ch.name, 0) + 1
        dup_names = [name for name, c in name_count.items() if c > 1]
        if dup_names:
            errors.append(f'角色未去重：{dup_names} 出现多次')

        # 3. 场景地点必须存在
        for s in scenes:
            if s.location_id not in loc_ids:
                errors.append(f'场景{s.scene_number} 引用不存在的地点 {s.location_id}')

        # 4. 场景元素类型合法
        valid_types = {'action', 'dialogue', 'transition', 'reveal'}
        for s in scenes:
            for el in s.elements:
                if el.type not in valid_types:
                    errors.append(f'场景{s.scene_number} 元素类型非法：{el.type}')

        # 5. 闪回场景不得为概括性单元素
        for s in scenes:
            if s.is_flashback and not s.elements:
                errors.append(f'闪回场景{s.scene_number} 无细节元素，未完整展开')

        # 6. 场景在场角色必须存在
        for s in scenes:
            for cid in s.characters_present:
                if cid not in char_ids:
                    errors.append(f'场景{s.scene_number} 在场角色 {cid} 不存在于世界书')

        # 7. 初始地点必须存在
        if st.player_location not in loc_ids:
            errors.append(f'初始地点 {st.player_location} 不存在于世界书')

        # 8. 初始在场角色必须存在
        for cid in st.present_characters:
            if cid not in char_ids:
                errors.append(f'初始在场角色 {cid} 不存在于世界书')

        # 9. 初始背包物品必须存在于某地点
        all_loc_items = {item for loc in wb.locations for item in loc.items}
        for item in st.inventory:
            if item not in all_loc_items:
                errors.append(f'初始背包物品 {item} 不存在于任何地点')

        # 10. 世界硬规则非空
        if not wb.rules:
            errors.append('世界书缺少硬规则（rules 为空）')

        # 11. manifest source_hash 一致
        manifest_text = read_text(path.join(self.output_dir, 'manifest.json'))
        if manifest_text:
            try:
                manifest = json.loads(manifest_text)
                if manifest.get('source_hash') != wb.source_hash:
                    errors.append('manifest source_hash 与世界书不一致')
            except json.JSONDecodeError:
                pass

        # 12. 无空场景
        for s in scenes:
            if not s.elements:
                errors.append(f'场景{s.scene_number} 无表现单元（空场景）')

        # 13. 对话元素必须带 speaker_id
        for s in scenes:
            for el in s.elements:
                if el.type == 'dialogue' and not el.speaker_id:
                    errors.append(f'场景{s.scene_number} 对话元素缺少 speaker_id')

        if errors:
            logger.error('资产包验收失败：')
            for e in errors:
                logger.error(f'  - {e}')
            self._write_state_marker('validated', detail='验收失败，详见日志')
            return False

        logger.info(
            f'✅ 资产包验收通过（{len(scenes)} 场景，{len(wb.characters)} 角色，{len(wb.locations)} 地点）'
        )
        self._write_state_marker('validated', detail='资产包验收通过')
        return True

    # ── 审批门禁（--approve-worldbook）───────────────────────

    def _approve_worldbook(self, worldbook: WorldBook) -> bool:
        """打印世界书摘要，交互式询问用户是否确认继续保存资产包。"""
        print('\n=== 世界书已抽取，请审核后再保存完整资产包 ===')
        print(f'  世界书文件：{path.join(self.output_dir, "worldbook.json")}')
        print(
            f'  角色数：{len(worldbook.characters)}，地点数：{len(worldbook.locations)}，'
            f'规则数：{len(worldbook.rules)}，势力数：{len(worldbook.factions)}'
        )
        print('  请检查上述文件内容，确认无误后再继续。')
        try:
            ans = input('是否确认 worldbook 并继续保存资产包？(y/n): ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        return ans == 'y'

    def _save_worldbook_only(self, worldbook: WorldBook) -> None:
        """仅保留 worldbook.json 供人工复核，停止于审批阶段。"""
        worldbook_fname = path.join(self.output_dir, 'worldbook.json')
        write_text(
            worldbook_fname,
            json.dumps(worldbook.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        logger.info(f'💾 已仅保留 worldbook.json：{worldbook_fname}')

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
        self._write_state_marker('loaded', detail=f'共 {len(chapters)} 章')

        source_hash = self._source_hash(chapters)
        if self.skip_existing and self._skip_if_cached(source_hash):
            self._write_state_marker('skipped', detail='source_hash 命中缓存')
            return

        full_text = '\n\n'.join(c.text for c in chapters)
        per_chapter = self.step_extract_all(chapters)
        self._write_state_marker('extracted', detail='分章抽取完成')

        worldbook = self.step_merge_entities(full_text, per_chapter)
        # 由编排器统一掌舵 source_hash（缓存失效与存档版本校验的依据）
        worldbook.source_hash = source_hash
        self._write_state_marker('merged', detail='跨章实体合并完成')

        # 审批门禁：人工确认 worldbook 后再继续
        if getattr(self.args, 'approve_worldbook', False):
            if not self._approve_worldbook(worldbook):
                # 仅保留 worldbook.json 供人工复核，停止于审批阶段
                self._save_worldbook_only(worldbook)
                self._write_state_marker(
                    'awaiting_approval', detail='用户未确认 worldbook，已暂停'
                )
                logger.info('⏭ 用户未确认 worldbook，停止于资产抽取阶段')
                return

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

        if getattr(self.args, 'validate', False):
            if not self.step_validate_assets(bundle):
                return

        self.step_save_assets(bundle)
        self._write_state_marker('saved', detail='资产包已保存')
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
    parser.add_argument(
        "--validate", action="store_true",
        help="保存前对资产包做~13项确定性验收，失败不退出码非零",
    )
    parser.add_argument(
        "--approve-worldbook", action="store_true",
        help="worldbook 生成后暂停，等待人工确认再保存完整资产包",
    )
    parser.set_defaults(func=gal_parse)
