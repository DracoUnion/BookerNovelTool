import json
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError, parse_obj_as

from .cross_anls_models import (
    CrossBookComparableFields,
    PatternCard,
    PatternLineage,
    ComparisonMatrix,
    ReuseRecommendation,
)
from .cross_anls_pmt import (
    TAG_EXTRACT_PMT, PATTERN_CARD_PMT, LINEAGE_PMT,
    COMPARISON_MATRIX_PMT, REUSE_RECOMMENDATION_PMT,
    TAG_EXTRACT_SYSTEM, PATTERN_CARD_SYSTEM, LINEAGE_SYSTEM,
    MATRIX_SYSTEM, RECOMMENDATION_SYSTEM,
    EMOTION_MODULE_POOL, RHYTHM_PATTERN_POOL,
    CONFLICT_TYPE_POOL, CHARACTER_ARCHETYPE_POOL,
    STYLE_POOL, APPLICABLE_SCENE_POOL,
)

from .openai import OpenAIClient
from .util import render_prompt, json_dump_model, ext_code_block

logger = logging.getLogger(__name__)


class CrossAnlsAgent:
    """统一封装跨书拆解分析的结构化 LLM 调用。"""

    def __init__(self, args):
        self.args = args
        self.model = args.model
        self.llm = OpenAIClient.from_args(args)

    def _call(
        self,
        pmt: str,
        response_model: Type[BaseModel],
        system_prompt: str,
        **ctx,
    ):
        """渲染提示词，发起一次结构化 LLM 调用并解析为 Pydantic 响应。"""
        user_prompt = render_prompt(pmt, **ctx)

        def parse(raw):
            data = json.loads(ext_code_block(raw))
            try:
                return parse_obj_as(response_model, data)
            except ValidationError as e:
                logger.warning(f"⚠️ 字段级解析警告：{[err['loc'] for err in e.errors()]}"
                               f" 将失败字段置 None 重试")
                for err in e.errors():
                    loc = err["loc"]
                    if not loc:
                        continue
                    top_key = loc[0]
                    if isinstance(data, dict) and top_key in data and data[top_key] is not None:
                        data[top_key] = None
                return parse_obj_as(response_model, data)

        return self.llm.call_llm_retry(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            self.model,
            retry=self.args.retry,
            temp=getattr(self.args, 'temp', 0.3),
            max_tokens=self.args.max_tokens,
            parse_output=parse,
        )

    def extract_tags(self, book_report: Dict[str, Any]) -> Optional[CrossBookComparableFields]:
        """从单书拆解结果提取标签与变体实例。"""
        return self._call(
            TAG_EXTRACT_PMT,
            CrossBookComparableFields,
            TAG_EXTRACT_SYSTEM,
            book_meta=json_dump_model(book_report.get('book_meta', {})),
            chapter_summaries=json_dump_model(book_report.get('chapter_summaries', [])),
            modules=json_dump_model(book_report.get('modules', {})),
            emotion_module_pool=", ".join(EMOTION_MODULE_POOL),
            rhythm_pattern_pool=", ".join(RHYTHM_PATTERN_POOL),
            conflict_type_pool=", ".join(CONFLICT_TYPE_POOL),
            character_archetype_pool=", ".join(CHARACTER_ARCHETYPE_POOL),
            style_pool=", ".join(STYLE_POOL),
            applicable_scene_pool=", ".join(APPLICABLE_SCENE_POOL),
        )

    def generate_pattern_card(
        self,
        tag_dimension: str,
        tag_value: str,
        variants: List[Dict[str, Any]],
    ) -> Optional[PatternCard]:
        """基于同一标签下的多书变体，生成模式卡片。"""
        return self._call(
            PATTERN_CARD_PMT,
            PatternCard,
            PATTERN_CARD_SYSTEM,
            tag_dimension=tag_dimension,
            tag_value=tag_value,
            variants=json_dump_model(variants),
        )

    def analyze_lineages(self, cards: List[PatternCard]) -> Optional[List[PatternLineage]]:
        """分析模式卡片之间的演化、冲突与互补关系。"""
        cards_summary = [
            {
                "pattern_card_id": c.pattern_card_id,
                "pattern_name": c.pattern_name,
                "tag_value": c.tag_value,
                "stable_elements": c.stable_elements,
                "variable_elements": c.variable_elements,
            }
            for c in cards
        ]
        return self._call(
            LINEAGE_PMT,
            List[PatternLineage],
            LINEAGE_SYSTEM,
            cards=json_dump_model(cards_summary),
        )

    def build_comparison_matrix(
        self,
        fields: List[CrossBookComparableFields],
    ) -> Optional[List[ComparisonMatrix]]:
        """基于全部书籍的可比字段，生成多维度对比矩阵。"""
        return self._call(
            COMPARISON_MATRIX_PMT,
            List[ComparisonMatrix],
            MATRIX_SYSTEM,
            fields=json_dump_model(fields),
        )

    def generate_reuse_recommendations(
        self,
        cards: List[PatternCard],
        matrix: List[ComparisonMatrix],
    ) -> Optional[List[ReuseRecommendation]]:
        """基于模式卡片与对比矩阵，给出按写新书场景组织的复用建议。"""
        cards_summary = [
            {
                "pattern_card_id": c.pattern_card_id,
                "pattern_name": c.pattern_name,
                "tag_dimension": c.tag_dimension,
                "tag_value": c.tag_value,
                "stable_elements": c.stable_elements,
                "variable_elements": c.variable_elements,
                "failure_modes": c.failure_modes,
            }
            for c in cards
        ]
        return self._call(
            REUSE_RECOMMENDATION_PMT,
            List[ReuseRecommendation],
            RECOMMENDATION_SYSTEM,
            cards=json_dump_model(cards_summary),
            matrix=json_dump_model(matrix),
        )
