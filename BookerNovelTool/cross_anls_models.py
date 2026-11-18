from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ──── 单书可比字段（第一层）────

class EmotionModuleInstance(BaseModel):
    tag: str
    description: str = Field(description="非原文描述")
    position: Literal["opening", "first_quarter", "middle", "last_quarter", "closing"]
    setup_chapters: int = Field(default=0, description="铺垫章数")
    payoff_chapter: int = Field(default=0, description="回报章号")
    aftermath_chapters: int = Field(default=0, description="余波章数")


class CrossBookComparableFields(BaseModel):
    # 身份锚定
    source_book_id: str = Field(description="书籍唯一标识")
    source_book_title: str = Field(description="书名")
    source_author: Optional[str] = Field(None, description="作者")
    source_edition: Optional[str] = Field(None, description="版本/来源")

    # 题材坐标
    genre_tags: List[str] = Field(default_factory=list, description="题材标签")
    subgenre_tags: List[str] = Field(default_factory=list, description="子题材标签")
    target_audience: Optional[str] = Field(None, description="目标受众")
    target_platform: Optional[str] = Field(None, description="目标平台")

    # 标签（LLM 提取或直接读取）
    emotion_module_tags: List[str] = Field(default_factory=list, description="情绪模块标签")
    rhythm_pattern_tags: List[str] = Field(default_factory=list, description="节奏模式标签")
    conflict_type_tags: List[str] = Field(default_factory=list, description="冲突类型标签")
    character_archetype_tags: List[str] = Field(default_factory=list, description="人物原型标签")
    style_label: Optional[str] = Field(None, description="文风标签")
    applicable_scene_tags: List[str] = Field(default_factory=list, description="适用场景标签")

    # 结构化数值（程序填充）
    climax_interval_distribution: Optional[Dict[str, Any]] = Field(None, description="高潮间隔分布")
    setup_payoff_ratio: Optional[float] = Field(None, description="铺垫回报比")
    dialogue_description_ratio: Optional[float] = Field(None, description="对话描写比")
    sentence_rhythm_profile: Optional[Dict[str, Any]] = Field(None, description="句式节奏画像")
    sensory_bias: List[str] = Field(default_factory=list, description="感官偏好")
    opening_type: Optional[str] = Field(None, description="开篇类型")
    structure_model: Optional[str] = Field(None, description="结构模型")
    pov_type: Optional[str] = Field(None, description="视角类型")

    # 变体实例（LLM 提取，供模式卡片使用）
    emotion_module_instances: List[EmotionModuleInstance] = Field(default_factory=list, description="情绪模块变体实例")

    # 可迁移性
    transferability_score: Optional[int] = Field(None, ge=1, le=5, description="可迁移性评分 1-5")
    prerequisite_setup: List[str] = Field(default_factory=list, description="前置铺垫要求")
    failure_modes: List[str] = Field(default_factory=list, description="失效模式")


# ──── 跨书聚合产物（第二层）────

class PatternVariant(BaseModel):
    variant_id: str = Field(description="变体唯一标识")
    source_book_id: str = Field(description="来源书籍 ID")
    source_chapter_index: Optional[int] = Field(None, description="来源章节号")
    description: str = Field(description="变体描述")
    distinguishing_feature: str = Field(description="区分特征")
    effectiveness_note: Optional[str] = Field(None, description="有效性备注")


class PatternDefinition(BaseModel):
    trigger: str = Field(description="触发条件")
    emotion_engine: str = Field(description="情绪引擎")
    payoff_mode: str = Field(description="回报模式")
    aftermath_handling: str = Field(description="余波处理")


class PatternCard(BaseModel):
    pattern_card_id: str = Field(description="模式卡片唯一标识")
    pattern_name: str = Field(description="模式名称")
    tag_dimension: Literal["emotion_module_tags", "rhythm_pattern_tags",
                           "conflict_type_tags", "character_archetype_tags"] = Field(description="标签维度")
    tag_value: str = Field(description="标签值")
    pattern_definition: PatternDefinition = Field(description="模式定义")
    pattern_variants: List[PatternVariant] = Field(default_factory=list, description="变体列表")
    variant_count: int = Field(default=0, description="变体数量")
    variant_axis: List[str] = Field(default_factory=list, description="变体差异维度")
    stable_elements: List[str] = Field(default_factory=list, description="稳定要素")
    variable_elements: List[str] = Field(default_factory=list, description="可变要素")
    effectiveness_distribution: Optional[Dict[str, Any]] = Field(None, description="有效性分布")
    failure_modes: List[str] = Field(default_factory=list, description="失效模式")


class PatternLineage(BaseModel):
    lineage_id: str = Field(description="谱系唯一标识")
    parent_pattern_id: str = Field(description="父模式 ID")
    child_pattern_ids: List[str] = Field(default_factory=list, description="子模式 ID 列表")
    relation_type: Literal["derives", "variant_of", "conflicts", "complements"] = Field(description="关系类型")
    note: Optional[str] = Field(None, description="备注")


class ComparisonMatrix(BaseModel):
    dimension: str = Field(description="对比维度名称")
    entries: List[Dict[str, Any]] = Field(default_factory=list, description="对比条目")
    dimension_ranking: Optional[List[str]] = Field(None, description="维度排名")


class ReuseRecommendation(BaseModel):
    scenario: str = Field(description="应用场景")
    recommended_pattern_ids: List[str] = Field(default_factory=list, description="推荐模式卡片 ID")
    reference_variant_ids: List[str] = Field(default_factory=list, description="参考变体 ID")
    avoid_failure_modes: List[str] = Field(default_factory=list, description="避免的失效模式")
    adaptation_notes: Optional[str] = Field(None, description="改编备注")


class QualityBaseline(BaseModel):
    dimension: str = Field(description="质量基线维度")
    median: Optional[float] = Field(None, description="中位数")
    p25: Optional[float] = Field(None, description="25 分位数")
    p75: Optional[float] = Field(None, description="75 分位数")
    sample_count: int = Field(default=0, description="样本数")


# ──── 数据集元信息与顶层报告────

class LoadedBookInfo(BaseModel):
    source_book_id: str = Field(description="书籍 ID")
    source_book_title: str = Field(description="书名")
    file_path: str = Field(description="文件路径")
    total_chapters: int = Field(description="总章节数")
    module_count: int = Field(description="模块数量")


class SkippedBookInfo(BaseModel):
    file_path: str = Field(description="文件路径")
    reason: str = Field(description="跳过原因")


class CrossBookDatasetMeta(BaseModel):
    input_dir: str = Field(description="输入目录")
    book_count: int = Field(description="加载书籍数")
    total_chapters: int = Field(description="总章节数")
    books_loaded: List[LoadedBookInfo] = Field(default_factory=list, description="已加载书籍")
    books_skipped: List[SkippedBookInfo] = Field(default_factory=list, description="跳过书籍")
    genre_distribution: Dict[str, int] = Field(default_factory=dict, description="题材分布")
    tag_coverage: Dict[str, int] = Field(default_factory=dict, description="标签覆盖统计")
    generated_at: str = Field(description="生成时间 ISO 格式")


class CrossBookAnalysisReport(BaseModel):
    dataset_meta: CrossBookDatasetMeta = Field(description="数据集元信息")
    comparable_fields: List[CrossBookComparableFields] = Field(default_factory=list, description="单书可比字段")
    pattern_cards: List[PatternCard] = Field(default_factory=list, description="模式卡片")
    pattern_lineages: List[PatternLineage] = Field(default_factory=list, description="模式谱系")
    comparison_matrix: List[ComparisonMatrix] = Field(default_factory=list, description="对比矩阵")
    reuse_recommendations: List[ReuseRecommendation] = Field(default_factory=list, description="复用建议")
    quality_baseline: List[QualityBaseline] = Field(default_factory=list, description="质量基线")