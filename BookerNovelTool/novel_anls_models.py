from typing import Any, Dict, List, Literal, Optional, Type, Union

from pydantic import BaseModel, Field


# ──── 基础数据模型 ────


class Chapter(BaseModel):
    """EPUB 解析出的单章"""

    index: int = Field(description="章节序号（从 1 开始）")
    title: str = Field(description="章节标题")
    text: str = Field(description="章节正文")


class BookMeta(BaseModel):
    """书籍元信息"""

    book_title: Optional[str] = None
    author: Optional[str] = None
    blurb: Optional[str] = None


# ──── 章节扫描子模型 ────


class CharacterBrief(BaseModel):
    """章节中登场的人物简述"""

    name: str = Field(description="角色名")
    role: str = Field(description="本章中呈现的角色定位")
    traits: List[str] = Field(default_factory=list, description="性格/特征")
    is_new: bool = Field(True, description="是否本章首次登场")


class PlotNode(BaseModel):
    """章节关键事件节点"""

    event_description: str = Field(description="事件描述")
    original_quote: Optional[str] = Field(None, description="原文引用")
    emotion_score: int = Field(0, ge=-9, le=9, description="情绪分 -9 到 +9")


class ParagraphFunctionTag(BaseModel):
    """段落功能标注"""

    paragraph_range: str = Field(description="段落区间")
    function_type: Literal["激励事件", "世界观渗透", "人物引入", "弧光推进", "钩子"] = Field(
        description="段落功能类型"
    )


class CharacterStateChange(BaseModel):
    """已有角色在本章的状态变化（处境/关系/认知三维）"""

    name: str = Field(description="角色名")
    situation: Optional[str] = Field(None, description="处境变化")
    relationship: Optional[str] = Field(None, description="关系变化")
    cognition: Optional[str] = Field(None, description="认知变化")


class ForeshadowingSet(BaseModel):
    """本章新埋设的伏笔"""

    content: str = Field(description="伏笔内容")
    planted_chapter: int = Field(description="埋设章号（当前章）")
    hint: Optional[str] = Field(None, description="提示")


class ForeshadowingPayoff(BaseModel):
    """本章回收的伏笔（只能回收之前章埋设的伏笔）"""

    content: str = Field(description="伏笔内容")
    set_chapter: int = Field(description="埋设章号（必须 ≤ 当前章号）")
    gap_chapters: int = Field(description="回收间隔章数")


# ──── 训练数据模型 ────


class TrainingSample(BaseModel):
    """章节级训练数据样本。字段存在即满足要求；大部分由数据 pipeline 填充。"""

    # ── 文本片段与切分（程序填充）──
    chunk_id: Optional[str] = None
    chunk_text: Optional[str] = None
    chunk_word_count: Optional[int] = None
    chunk_start_paragraph: Optional[int] = None
    chunk_end_paragraph: Optional[int] = None
    segmentation_strategy: Optional[Literal["natural_paragraph", "scene_boundary", "sliding_window"]] = None
    overlap_paragraphs: Optional[int] = None
    semantic_coherence_score: Optional[float] = None

    # ── 指令与任务构造（LLM 可生成 / 模板填充）──
    instruction: Optional[str] = None
    instruction_type: Optional[Literal["续写", "改写", "风格迁移", "情节扩写", "对话生成", "伏笔回收"]] = None
    input: Optional[str] = None
    system_prompt: Optional[str] = None
    prompt_template_id: Optional[str] = None
    output: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None

    # ── 风格迁移专用 ──
    style_label: Optional[str] = None
    source_style_label: Optional[str] = None
    style_features: Optional[Dict[str, Any]] = None
    content_description: Optional[str] = None

    # ── DPO 偏好数据 ──
    prompt: Optional[str] = None
    chosen: Optional[str] = None
    rejected: Optional[str] = None
    preference_dimension: Optional[
        Literal["style_fidelity", "plot_reasonableness", "character_consistency", "rhythm_control", "avoid_ai_tone", "avoid_cliche"]
    ] = None
    preference_strength: Optional[int] = Field(None, ge=1, le=5)
    preference_source: Optional[Literal["human", "editor", "rule", "strong_model"]] = None

    # ── Agent 轨迹 ──
    observation: Optional[str] = None
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    action_output: Optional[Dict[str, Any]] = None
    step_index: Optional[int] = None
    is_terminal: Optional[bool] = None

    # ── 质量与合规 ──
    quality_scores: Optional[Dict[str, int]] = None
    overall_quality: Optional[float] = None
    duplicate_flag: Optional[bool] = None
    copyright_risk: Optional[Literal["safe", "needs_review", "blocked"]] = None
    pii_removed: Optional[bool] = None
    source_trace: Optional[Dict[str, Any]] = None

    # ── 格式与配置 ──
    data_format: Optional[Literal["chatml", "alpaca", "sharegpt", "dpo_pair"]] = None
    language: Optional[str] = None
    split: Optional[Literal["train", "val", "test"]] = None
    sample_weight: Optional[float] = None


class TrainingDatasetMeta(BaseModel):
    """全书级训练数据集元信息。字段存在即满足要求；由 orchestrator 汇总填充。"""

    # ── 数据集构成 ──
    dataset_name: Optional[str] = None
    dataset_version: Optional[str] = None
    total_samples: Optional[int] = None
    sample_count_by_task: Optional[Dict[str, int]] = None
    chunk_count: Optional[int] = None
    avg_chunk_word_count: Optional[float] = None
    prompt_template_coverage: Optional[Dict[str, int]] = None
    genre_distribution: Optional[Dict[str, float]] = None
    source_book_count: Optional[int] = None

    # ── 全书级训练目标 ──
    book_level_instruction: Optional[str] = None
    book_level_output: Optional[str] = None
    style_profile: Optional[Dict[str, Any]] = None
    plot_summary_for_style: Optional[str] = None

    # ── 偏好与对齐 ──
    book_level_chosen: Optional[str] = None
    book_level_rejected: Optional[str] = None
    preference_rubric: Optional[Dict[str, Any]] = None

    # ── 合规与溯源 ──
    license: Optional[str] = None
    copyright_review_status: Optional[str] = None
    dedup_report: Optional[Dict[str, Any]] = None
    audit_sample_rate: Optional[float] = None
    data_origin_pipeline: Optional[str] = None


# ──── 章节扫描模型 ────


class ChapterSummary(BaseModel):
    module: Literal["章节摘要"] = "章节摘要"
    # 改名
    chapter_index: int = Field(description="章节序号")
    chapter_title: Optional[str] = Field(None, description="章节标题")
    chapter_summary: str = Field(description="50字以内核心摘要")
    # 保留
    word_count: int = Field(description="本章字数")
    emotional_tone: int = Field(ge=0, le=10, description="情绪基调 0-10")
    chapter_end_hook: Optional[str] = Field(None, description="章尾钩子")
    conflict_level: int = Field(ge=0, le=10, description="冲突烈度 0-10")

    # P0 新增
    plot_node_list: List[PlotNode] = Field(default_factory=list, description="本章关键事件节点")
    character_list: List[CharacterBrief] = Field(default_factory=list, description="本章登场人物")
    character_state_change: List[CharacterStateChange] = Field(
        default_factory=list, description="已有角色状态变化"
    )
    foreshadowing_set: List[ForeshadowingSet] = Field(default_factory=list, description="新埋伏笔")
    foreshadowing_payoff: List[ForeshadowingPayoff] = Field(
        default_factory=list, description="本章回收的伏笔"
    )
    core_trope_usage_density: int = Field(0, ge=0, le=10, description="核心套路使用密度 0-10")
    chapter_end_hook_type: Optional[
        Literal["info_suspense", "emotion_suspense", "situational_suspense", "emotion_closure"]
    ] = Field(None, description="章尾钩子类型")
    situation_change: Optional[Literal["positive", "negative", "neutral"]] = None
    relationship_change: Optional[Literal["positive", "negative", "neutral"]] = None
    cognition_change: Optional[Literal["positive", "negative", "neutral"]] = None
    emotion_direction: Optional[Literal["up", "down", "flat", "fluctuating"]] = None
    perceptible_change_flag: bool = Field(False, description="本章是否发生可感知变化")
    dialogue_ratio: Optional[float] = Field(None, ge=0, le=1, description="对话占比 0-1")
    description_density: Optional[float] = Field(None, ge=0, le=1, description="描写密度 0-1")
    timeline_node: Optional[str] = Field(None, description="时间线节点")

    # P1 新增
    sentence_pattern_features: Optional[Dict[str, Any]] = None

    # P2 新增（开关化）
    source_page_range: Optional[str] = None
    chapter_title_style_type: Optional[
        Literal["sensory", "event", "state", "suspense", "closure"]
    ] = None
    paragraph_function_tags: List[ParagraphFunctionTag] = Field(default_factory=list)
    key_dialogue_excerpt: List[str] = Field(default_factory=list)
    dialogue_iceberg_check: Optional[Dict[str, Any]] = None
    sensory_preference: List[str] = Field(default_factory=list)

    # 训练数据嵌套字段（本次必须存在；P2 生成或后填）
    training_sample: Optional[TrainingSample] = None


class BookAnalysisReport(BaseModel):
    """完整分析报告"""

    book_meta: BookMeta
    total_chapters: int
    chapter_summaries: List["ChapterSummary"] = Field(default_factory=list)
    modules: Dict[str, Any] = Field(default_factory=dict)
    training_dataset_meta: Optional[TrainingDatasetMeta] = None


# ──── 全书级模块模型 ────


class GenreModule(BaseModel):
    module: Literal["题材与定位"] = "题材与定位"
    genre_tags: List[str] = Field(default_factory=list, description="题材标签")
    target_audience: Optional[str] = None
    market_position: Optional[str] = None
    unique_selling_point: Optional[str] = None
    target_platform: Optional[str] = None
    core_trope: Optional[str] = None


class TitleModule(BaseModel):
    module: Literal["书名与简介"] = "书名与简介"
    title_analysis: Optional[Dict[str, Any]] = None
    blurb_hooks: Optional[List[str]] = None
    blurb_effectiveness: Optional[str] = None
    one_sentence_pitch: Optional[str] = None


class WorldModule(BaseModel):
    module: Literal["世界观设定"] = "世界观设定"
    core_rules: Optional[str] = None
    factions: Optional[List[Dict[str, str]]] = None
    unique_elements: Optional[List[str]] = None
    logic_consistency: Optional[str] = None
    world_immersion_score: Optional[int] = None
    story_core: Optional[str] = None
    core_theme: Optional[str] = None


class CharacterModule(BaseModel):
    module: Literal["人物图谱"] = "人物图谱"
    protagonist: Optional[Dict[str, Any]] = None
    supporting_chars: Optional[List[Dict[str, Any]]] = None
    antagonist: Optional[Dict[str, Any]] = None
    character_relationship_graph: Optional[Dict[str, Any]] = None
    character_profile: Optional[Dict[str, Any]] = None
    character_arc: Optional[Dict[str, Any]] = None
    relationship_progression_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    ensemble_function_classification: Optional[Dict[str, Any]] = None
    dual_desire_design_validation: Optional[Dict[str, Any]] = None


class StructureModule(BaseModel):
    module: Literal["主线与结构"] = "主线与结构"
    main_storyline: Optional[str] = None
    structure: Optional[Dict[str, Any]] = None
    subplots: Optional[List[Dict[str, str]]] = None
    structure_score: Optional[int] = None
    seven_step_structure_analysis: Optional[Dict[str, Any]] = None
    inciting_incident_analysis: Optional[str] = None
    eight_act_structure_overview: List[Dict[str, Any]] = Field(default_factory=list)
    gap_progression_mechanism: Optional[str] = None
    three_layer_conflict_rule: Optional[Dict[str, Any]] = None
    antagonistic_force_escalation_path: Optional[str] = None


class RhythmModule(BaseModel):
    module: Literal["节奏与爽点"] = "节奏与爽点"
    climax_points: Optional[List[Dict[str, Any]]] = None
    flat_periods: Optional[List[Dict[str, str]]] = None
    emotion_curve: Optional[Union[str, List[Dict[str, Any]]]] = None
    rhythm_score: Optional[int] = None
    rhythm_map: List[Dict[str, Any]] = Field(default_factory=list)
    selling_point_cycle_pattern: Optional[Dict[str, Any]] = None
    core_emotion_self_check_result: Optional[Dict[str, Any]] = None


class GimmickModule(BaseModel):
    module: Literal["金手指/核心创意"] = "金手指/核心创意"
    unique_setting: Optional[str] = None
    innovation: Optional[str] = None
    core_gimmick: Optional[str] = None
    creativity_score: Optional[int] = None
    execution_score: Optional[int] = None


class OpeningModule(BaseModel):
    module: Literal["开篇钩子"] = "开篇钩子"
    first_500_words_hook: Optional[str] = None
    protagonist_first_impression: Optional[str] = None
    chapter_end_hooks: Optional[List[Dict[str, Any]]] = None
    golden_three_effectiveness: Optional[str] = None
    drop_off_risk: Optional[str] = None


class ForeshadowModule(BaseModel):
    module: Literal["伏笔与铺垫"] = "伏笔与铺垫"
    foreshadowing_list: Optional[List[Dict[str, Any]]] = None
    information_asymmetry: Optional[str] = None
    continuity: Optional[str] = None
    foreshadowing_score: Optional[int] = None
    foreshadowing_master_table: List[Dict[str, Any]] = Field(default_factory=list)
    scattered_plot_fallback_list: List[str] = Field(default_factory=list)


class PatternModule(BaseModel):
    module: Literal["可迁移模式"] = "可迁移模式"
    structural_patterns: Optional[List[str]] = None
    character_patterns: Optional[List[str]] = None
    rhythm_patterns: Optional[List[str]] = None
    writing_techniques: Optional[List[str]] = None
    imitation_advice: Optional[str] = None


class StyleModule(BaseModel):
    module: Literal["文风与语言"] = "文风与语言"
    narrative_pov: Optional[str] = None
    dialogue_technique_summary: Optional[str] = None
    sentence_and_style_review: Optional[str] = None
    language_fingerprint: Optional[Dict[str, Any]] = None
    motif_image_system: List[str] = Field(default_factory=list)
    style_boundary: List[str] = Field(default_factory=list)


class RatingModule(BaseModel):
    module: Literal["综合评分"] = "综合评分"
    seven_dimension_rating: Optional[Dict[str, int]] = None
    structure_review: Optional[Dict[str, Any]] = None
    one_sentence_summary: Optional[str] = None


MODULE_CLASS_MAP: Dict[str, Type[BaseModel]] = {
    "题材与定位": GenreModule,
    "书名与简介": TitleModule,
    "世界观设定": WorldModule,
    "人物图谱": CharacterModule,
    "主线与结构": StructureModule,
    "节奏与爽点": RhythmModule,
    "金手指/核心创意": GimmickModule,
    "开篇钩子": OpeningModule,
    "伏笔与铺垫": ForeshadowModule,
    "可迁移模式": PatternModule,
    "文风与语言": StyleModule,
    "综合评分": RatingModule,
}

# 解析前向引用（BookAnalysisReport 对 ChapterSummary 的字符串引用）
BookAnalysisReport.model_rebuild()
