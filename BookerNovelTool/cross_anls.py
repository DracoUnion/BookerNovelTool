import hashlib
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from os import path
from statistics import median, quantiles
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .cross_anls_models import (
    CrossBookComparableFields,
    CrossBookDatasetMeta,
    CrossBookAnalysisReport,
    LoadedBookInfo,
    PatternCard,
    PatternLineage,
    ComparisonMatrix,
    QualityBaseline,
    ReuseRecommendation,
    SkippedBookInfo,
)
from .cross_anls_agent import CrossAnlsAgent
from .util import json_dump_model

logger = logging.getLogger(__name__)

OUTPUT_FILENAME_PATTERN = re.compile(r"cross_book_analysis\..*")
SUPPORTED_EXTENSIONS = (".json", ".yaml", ".yml")


class CrossAnlsOrchestrator:
    """负责扫描单书拆解结果、标签提取、模式卡片生成、报告组装与保存。"""

    def __init__(self, args):
        self.args = args
        self.input_dir = args.dir
        self.output_path = args.output or path.join(self.input_dir, "cross_book_analysis.json")
        self.max_workers = args.threads
        self.agent = CrossAnlsAgent(args)

        self.loaded_books: List[LoadedBookInfo] = []
        self.skipped_books: List[SkippedBookInfo] = []
        self.book_reports: List[Dict[str, Any]] = []
        self.comparable_fields: List[CrossBookComparableFields] = []
        self.pattern_cards: List[PatternCard] = []
        self.lineages: List[PatternLineage] = []
        self.matrix: List[ComparisonMatrix] = []
        self.recommendations: List[ReuseRecommendation] = []
        self.quality_baseline: List[QualityBaseline] = []
        self._pending_card_groups: List[Tuple[str, str, List[Dict[str, Any]]]] = []

    # ── 阶段一：扫描与加载 ────

    def _iter_input_files(self):
        """遍历目录下的 JSON/YAML 文件，排除自身输出文件；honor --recursive."""
        if path.isfile(self.input_dir):
            yield self.input_dir
            return

        if getattr(self.args, "recursive", False):
            for root, _dirs, names in os.walk(self.input_dir):
                for name in names:
                    yield path.join(root, name)
        else:
            for name in os.listdir(self.input_dir):
                yield path.join(self.input_dir, name)

    @staticmethod
    def _load_report(file_path: str) -> Optional[Dict[str, Any]]:
        """加载单个单书拆解结果文件（JSON 或 YAML）。"""
        try:
            if file_path.lower().endswith(".json"):
                with open(file_path, encoding="utf8") as f:
                    return json.load(f)
            with open(file_path, encoding="utf8") as f:
                return yaml.safe_load(f)
        except Exception as error:  # noqa: BLE001
            logger.warning(f"⚠️ 无法加载 {file_path}: {error}")
            return None

    @staticmethod
    def _derive_book_id(report: Dict[str, Any], file_path: str) -> str:
        """派生书籍唯一标识：优先读取 source_book_id，否则 md5(书名|作者) 前 12 位。"""
        existing = report.get("source_book_id") if isinstance(report, dict) else None
        if existing:
            return str(existing)
        meta = report.get("book_meta", {}) if isinstance(report, dict) else {}
        title = str(meta.get("book_title") or path.splitext(path.basename(file_path))[0])
        author = str(meta.get("author") or "")
        return hashlib.md5(f"{title}|{author}".encode("utf8")).hexdigest()[:12]

    def _stage1_scan_and_load(self) -> None:
        """阶段一：扫描目录并加载单书拆解结果。"""
        logger.info(f"🔍 阶段一：扫描目录 {self.input_dir}")
        if not path.exists(self.input_dir):
            logger.fatal(f"目录不存在: {self.input_dir}")
            return

        loaded: List[LoadedBookInfo] = []
        skipped: List[SkippedBookInfo] = []
        reports: List[Dict[str, Any]] = []

        for file_path in self._iter_input_files():
            if not path.isfile(file_path):
                continue
            if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
                continue
            if OUTPUT_FILENAME_PATTERN.match(path.basename(file_path)):
                continue

            report = self._load_report(file_path)
            if not isinstance(report, dict) or not (
                report.get("book_meta") or report.get("chapter_summaries")
            ):
                skipped.append(SkippedBookInfo(file_path=file_path, reason="缺少 book_meta 或 chapter_summaries"))
                continue

            book_id = self._derive_book_id(report, file_path)
            meta = report.get("book_meta", {}) or {}
            chapters = report.get("chapter_summaries", []) or []
            modules = report.get("modules", {}) or {}
            loaded.append(LoadedBookInfo(
                source_book_id=book_id,
                source_book_title=str(meta.get("book_title") or path.splitext(path.basename(file_path))[0]),
                file_path=file_path,
                total_chapters=len(chapters),
                module_count=len(modules),
            ))
            reports.append(report)

        self.loaded_books = loaded
        self.skipped_books = skipped
        self.book_reports = reports

        for info in loaded:
            logger.info(f"  ✅ 加载: {info.source_book_title} ({info.source_book_id}, {info.total_chapters} 章)")
        for info in skipped:
            logger.warning(f"  ⏭ 跳过: {info.file_path} ({info.reason})")

        if len(loaded) < self.args.min_books:
            logger.warning(
                f"⚠️ 加载书籍数 {len(loaded)} 少于最少书籍数 {self.args.min_books}，仍继续执行"
            )
        logger.info(f"✅ 阶段一完成，加载 {len(loaded)} 本书，跳过 {len(skipped)} 个文件")

    # ── 阶段二：逐书标签提取（并行）────

    @staticmethod
    def _compute_structure_fields(report: Dict[str, Any]) -> Dict[str, Any]:
        """从 chapter_summaries 与 modules 中程序计算结构化数值字段，不依赖 LLM。"""
        chapter_summaries = report.get("chapter_summaries", []) or []
        modules = report.get("modules", {}) or {}

        dialogue_ratios = [
            s.get("dialogue_ratio") for s in chapter_summaries
            if isinstance(s, dict) and isinstance(s.get("dialogue_ratio"), (int, float))
        ]
        description_densities = [
            s.get("description_density") for s in chapter_summaries
            if isinstance(s, dict) and isinstance(s.get("description_density"), (int, float))
        ]

        dialogue_description_ratio = None
        if dialogue_ratios and description_densities:
            avg_dialogue = sum(dialogue_ratios) / len(dialogue_ratios)
            avg_description = sum(description_densities) / len(description_densities)
            if avg_description:
                dialogue_description_ratio = round(avg_dialogue / avg_description, 4)

        # 高潮间隔分布：依据章节级 conflict_level >= 8 的章位置间隔
        climax_chapters = [
            idx + 1 for idx, s in enumerate(chapter_summaries)
            if isinstance(s, dict) and isinstance(s.get("conflict_level"), (int, float)) and s["conflict_level"] >= 8
        ]
        intervals = [
            climax_chapters[i + 1] - climax_chapters[i]
            for i in range(len(climax_chapters) - 1)
        ]
        climax_interval_distribution = None
        if intervals:
            climax_interval_distribution = {
                "climax_chapters": climax_chapters,
                "intervals": intervals,
                "avg_interval": round(sum(intervals) / len(intervals), 2),
            }

        # 铺垫回报比：依据伏笔埋设/回收间隔（若存在伏笔与铺垫模块）
        setup_payoff_ratio = None
        foreshadow = modules.get("伏笔与铺垫") if isinstance(modules, dict) else None
        if isinstance(foreshadow, dict):
            table = foreshadow.get("foreshadowing_master_table") or []
            gaps = [
                item.get("gap_chapters") for item in table
                if isinstance(item, dict) and isinstance(item.get("gap_chapters"), (int, float))
            ]
            if gaps:
                setup_payoff_ratio = round(sum(gaps) / len(gaps), 2)

        # 句式节奏画像：来自章节级 sentence_pattern_features
        sentence_rhythm_profile = None
        features = [
            s.get("sentence_pattern_features") for s in chapter_summaries
            if isinstance(s, dict) and isinstance(s.get("sentence_pattern_features"), dict)
        ]
        if features:
            sentence_rhythm_profile = {"samples": len(features), "features": features[:5]}

        sensory_bias: List[str] = []
        for s in chapter_summaries:
            if isinstance(s, dict) and isinstance(s.get("sensory_preference"), list):
                sensory_bias.extend(s["sensory_preference"])

        # 开篇类型：来自开篇钩子模块
        opening_type = None
        opening = modules.get("开篇钩子") if isinstance(modules, dict) else None
        if isinstance(opening, dict):
            opening_type = opening.get("first_500_words_hook") or opening.get("golden_three_effectiveness")

        # 结构模型：来自主线与结构模块
        structure_model = None
        structure = modules.get("主线与结构") if isinstance(modules, dict) else None
        if isinstance(structure, dict):
            structure_model = structure.get("structure") or structure.get("eight_act_structure_overview")
            if isinstance(structure_model, (list, dict)):
                structure_model = json_dump_model(structure_model)
            structure_model = str(structure_model) if structure_model else None

        # 视角类型：来自文风与语言模块
        pov_type = None
        style = modules.get("文风与语言") if isinstance(modules, dict) else None
        if isinstance(style, dict):
            pov_type = style.get("narrative_pov")

        return {
            "climax_interval_distribution": climax_interval_distribution,
            "setup_payoff_ratio": setup_payoff_ratio,
            "dialogue_description_ratio": dialogue_description_ratio,
            "sentence_rhythm_profile": sentence_rhythm_profile,
            "sensory_bias": sensory_bias,
            "opening_type": opening_type,
            "structure_model": structure_model,
            "pov_type": pov_type,
        }

    def _stage2_extract_tags(self) -> None:
        """阶段二：逐书标签提取（并行），随后程序补充结构化数值字段。"""
        if self.args.skip_tag_extraction:
            logger.info("⏭ 阶段二：跳过标签提取（--skip-tag-extraction），直接读取 book_reports 中的 comparable_fields")
            for report in self.book_reports:
                fields = report.get("comparable_fields")
                if isinstance(fields, dict):
                    fields["source_book_id"] = fields.get("source_book_id") or self._derive_book_id(
                        report, report.get("_file_path", "")
                    )
                    self.comparable_fields.append(CrossBookComparableFields(**fields))
            return

        logger.info(f"🏷 阶段二：并行提取标签（共 {len(self.book_reports)} 本，并发数 {self.max_workers}）")

        def _extract_one(report: Dict[str, Any]) -> Optional[CrossBookComparableFields]:
            try:
                fields = self.agent.extract_tags(report)
                if fields is None:
                    title = (report.get("book_meta") or {}).get("book_title")
                    logger.warning(f"⚠️ 标签提取返回空：{title}")
                    return None
                struct = self._compute_structure_fields(report)
                for key, value in struct.items():
                    if getattr(fields, key) is None:
                        setattr(fields, key, value)
                return fields
            except Exception as error:  # noqa: BLE001
                title = (report.get("book_meta") or {}).get("book_title")
                logger.warning(f"⚠️ 标签提取失败（{title}）：{error}")
                return None

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_extract_one, report) for report in self.book_reports]
            for future in as_completed(futures):
                fields = future.result()
                if fields is not None:
                    self.comparable_fields.append(fields)

        self.comparable_fields.sort(key=lambda f: f.source_book_id)
        logger.info(f"✅ 阶段二完成，产出 {len(self.comparable_fields)} 份可比字段")

    # ── 阶段三：模式卡片生成（并行，按 focus_tags）────

    def _stage3_pattern_cards(self) -> None:
        """阶段三：按 focus_tags 分组生成模式卡片，仅对变体数 ≥ 2 的组生成。"""
        logger.info("🃏 阶段三：生成模式卡片")

        focus_tags = getattr(self.args, "focus_tags", ["emotion_module_tags"]) or ["emotion_module_tags"]

        groups: Dict[str, List[Dict[str, Any]]] = {}
        for fields in self.comparable_fields:
            for tag_dimension in focus_tags:
                tag_values = getattr(fields, tag_dimension, []) or []
                instances = getattr(fields, "emotion_module_instances", []) or []
                for tag_value in tag_values:
                    groups.setdefault(f"{tag_dimension}\x01{tag_value}", []).append({
                        "variant_id": f"{fields.source_book_id}_{tag_dimension}_{tag_value}",
                        "source_book_id": fields.source_book_id,
                        "source_chapter_index": None,
                        "description": "",
                        "distinguishing_feature": "",
                        "effectiveness_note": None,
                        "tag_dimension": tag_dimension,
                        "tag_value": tag_value,
                    })
                # 情绪模块变体实例作为更丰富的变体来源（仅情绪模块维度）
                if tag_dimension == "emotion_module_tags":
                    for inst in instances:
                        if inst.tag in tag_values:
                            groups.setdefault(f"{tag_dimension}\x01{inst.tag}", []).append({
                                "variant_id": f"{fields.source_book_id}_{inst.tag}_{inst.position or 'x'}",
                                "source_book_id": fields.source_book_id,
                                "source_chapter_index": None,
                                "description": inst.description,
                                "distinguishing_feature": inst.position or "",
                                "effectiveness_note": None,
                                "tag_dimension": tag_dimension,
                                "tag_value": inst.tag,
                            })

        self._pending_card_groups = []
        for key, variants in groups.items():
            tag_dimension, tag_value = key.split("\x01", 1)
            if tag_dimension not in set(focus_tags):
                continue
            if len(variants) < 2:
                logger.debug(f"⏭ 跳过 {tag_dimension}/{tag_value}：变体数 {len(variants)} < 2")
                continue
            self._pending_card_groups.append((tag_dimension, tag_value, variants))

        if not self._pending_card_groups:
            logger.info("✅ 阶段三：无满足变体数 ≥ 2 的标签组，跳过模式卡片生成")
            return

        logger.info(f"  待生成模式卡片组数：{len(self._pending_card_groups)}")

        def _generate_one(group) -> Optional[PatternCard]:
            tag_dimension, tag_value, variants = group
            try:
                card = self.agent.generate_pattern_card(tag_dimension, tag_value, variants)
                if card is None:
                    logger.warning(f"⚠️ 模式卡片生成返回空：{tag_dimension}/{tag_value}")
                    return None
                card.pattern_card_id = f"{tag_dimension}_{tag_value}_{len(self.pattern_cards) + 1}"
                card.variant_count = len(variants)
                return card
            except Exception as error:  # noqa: BLE001
                logger.warning(f"⚠️ 模式卡片生成失败（{tag_dimension}/{tag_value}）：{error}")
                return None

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_generate_one, g) for g in self._pending_card_groups]
            for future in as_completed(futures):
                card = future.result()
                if card is not None:
                    self.pattern_cards.append(card)

        self.pattern_cards.sort(key=lambda c: c.pattern_card_id)
        logger.info(f"✅ 阶段三完成，生成 {len(self.pattern_cards)} 张模式卡片")

    # ── 阶段四：谱系 + 对比矩阵 + 复用建议（串行）────

    def _stage4_aggregate(self) -> None:
        """阶段四：谱系、对比矩阵、复用建议（串行 LLM 调用）+ 程序计算质量基线。"""
        logger.info("🔗 阶段四：谱系 + 对比矩阵 + 复用建议")

        self.lineages = self.agent.analyze_lineages(self.pattern_cards) or []
        logger.info(f"  模式谱系：{len(self.lineages)} 条")

        self.matrix = self.agent.build_comparison_matrix(self.comparable_fields) or []
        logger.info(f"  对比矩阵维度：{len(self.matrix)} 个")

        self.recommendations = self.agent.generate_reuse_recommendations(self.pattern_cards, self.matrix) or []
        logger.info(f"  复用建议：{len(self.recommendations)} 条")

        self._compute_quality_baseline()
        logger.info(f"  质量基线维度：{len(self.quality_baseline)} 个")

    def _compute_quality_baseline(self) -> None:
        """程序计算质量基线：对对比矩阵中各数值维度求 median / p25 / p75。"""
        baselines: List[QualityBaseline] = []
        for matrix_dim in self.matrix:
            values = []
            for entry in matrix_dim.entries:
                value = entry.get("value")
                if isinstance(value, (int, float)):
                    values.append(float(value))
            if not values:
                continue
            values.sort()
            med = median(values)
            qs = quantiles(values, n=4) if len(values) >= 4 else [values[0], med, values[-1]]
            baselines.append(QualityBaseline(
                dimension=matrix_dim.dimension,
                median=round(med, 4),
                p25=round(qs[0], 4),
                p75=round(qs[2], 4),
                sample_count=len(values),
            ))
        self.quality_baseline = baselines

    # ── 阶段五：组装与保存 ────

    def _stage5_assemble_and_save(self) -> None:
        """阶段五：组装 CrossBookAnalysisReport 并写入 JSON。"""
        genre_distribution: Dict[str, int] = {}
        tag_coverage: Dict[str, int] = {
            "emotion_module_tags": 0,
            "rhythm_pattern_tags": 0,
            "conflict_type_tags": 0,
            "character_archetype_tags": 0,
        }
        total_chapters = 0

        for fields in self.comparable_fields:
            for genre in fields.genre_tags:
                genre_distribution[genre] = genre_distribution.get(genre, 0) + 1
            for dim in tag_coverage:
                if getattr(fields, dim, []):
                    tag_coverage[dim] += 1

        for info in self.loaded_books:
            total_chapters += info.total_chapters

        dataset_meta = CrossBookDatasetMeta(
            input_dir=self.input_dir,
            book_count=len(self.loaded_books),
            total_chapters=total_chapters,
            books_loaded=self.loaded_books,
            books_skipped=self.skipped_books,
            genre_distribution=genre_distribution,
            tag_coverage=tag_coverage,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        report = CrossBookAnalysisReport(
            dataset_meta=dataset_meta,
            comparable_fields=self.comparable_fields,
            pattern_cards=self.pattern_cards,
            pattern_lineages=self.lineages,
            comparison_matrix=self.matrix,
            reuse_recommendations=self.recommendations,
            quality_baseline=self.quality_baseline,
        )

        out_dir = path.dirname(self.output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(self.output_path, "w", encoding="utf8") as f:
            json.dump(report.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        logger.info("💾 阶段五：报告已保存")
        logger.info(f"  加载书数：{len(self.loaded_books)}")
        logger.info(f"  跳过书数：{len(self.skipped_books)}")
        logger.info(f"  模式卡片数：{len(self.pattern_cards)}")
        logger.info(f"  谱系数：{len(self.lineages)}")
        logger.info(f"  矩阵维度数：{len(self.matrix)}")
        logger.info(f"  建议数：{len(self.recommendations)}")
        logger.info(f"  输出路径：{self.output_path}")

    def run(self) -> None:
        """主流程：依次执行阶段一至五。"""
        self._stage1_scan_and_load()
        self._stage2_extract_tags()
        self._stage3_pattern_cards()
        self._stage4_aggregate()
        self._stage5_assemble_and_save()


def cross_anls(args):
    """CLI 入口函数。"""
    orchestrator = CrossAnlsOrchestrator(args)
    orchestrator.run()


def reg_subparser(subparsers):
    parser = subparsers.add_parser(
        "cross-anls",
        help="跨书拆解分析：扫描目录中的单书拆解结果（JSON/YAML），聚合为跨书素材库",
    )
    parser.add_argument("dir", help="包含单书拆解结果（JSON/YAML）的目录")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件路径（默认 <dir>/cross_book_analysis.json）")
    parser.add_argument("-t", "--threads", type=int, default=8,
                        help="并行线程数")
    parser.add_argument("--min-books", type=int, default=2,
                        help="最少书籍数，少于该值时仅警告不中断")
    parser.add_argument("--recursive", action="store_true",
                        help="递归扫描子目录")
    parser.add_argument("--skip-tag-extraction", action="store_true",
                        help="跳过标签提取（单书结果已含跨书标签字段时使用）")
    parser.add_argument("--focus-tags", nargs="+", default=["emotion_module_tags"],
                        choices=["emotion_module_tags", "rhythm_pattern_tags",
                                 "conflict_type_tags", "character_archetype_tags"],
                        help="生成模式卡片的标签维度（默认仅情绪模块）")
    parser.set_defaults(func=cross_anls)
