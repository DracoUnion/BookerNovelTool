#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LLM 语义指标的 Pydantic 响应模型（C 档直接输出 / D 档 LLM 分支输出）。

所有字段带中文 description，沿用项目 `Field(..., description=...)` 约定。
字段尽量提供默认值，避免单次解析失败导致整轮重试。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

AnyDict = Dict[str, Any]

# ──── C 档：逐段/全文语义分析 ────


class RhetoricResult(BaseModel):
    """修辞手法识别结果。"""

    simile: int = Field(0, description="明喻数量")
    metaphor: int = Field(0, description="暗喻/隐喻数量")
    personification: int = Field(0, description="拟人数量")
    exaggeration: int = Field(0, description="夸张数量")
    parallelism: int = Field(0, description="排比数量")
    repetition: int = Field(0, description="反复数量")
    irony: int = Field(0, description="反讽/讽刺数量")
    pun: int = Field(0, description="双关数量")
    symbolism: int = Field(0, description="象征数量")
    synaesthesia: int = Field(0, description="通感数量")
    examples: List[AnyDict] = Field(
        default_factory=list, description="修辞实例列表，每项含 type 与 text"
    )
    rhetoric_density: float = Field(0, description="修辞密度 0-1")
    confidence: float = Field(0, description="置信度 0-1")


class DescriptionResult(BaseModel):
    """句子描写类型分布。"""

    counts: Dict[str, int] = Field(
        default_factory=dict,
        description="各类型句数：psych/action/environment/dialogue/narration",
    )
    ratios: Dict[str, float] = Field(
        default_factory=dict,
        description="各类型比例 0-1：psych/action/environment/dialogue/narration",
    )
    confidence: float = Field(0, description="置信度 0-1")


class NarrativeResult(BaseModel):
    """叙事学特征。"""

    person: str = Field("", description="人称：第一/二/三人称")
    viewpoint: str = Field("", description="视角：限知/全知/客观/混合")
    perspective_entity: str = Field("", description="视角主体（谁在看）")
    narration_time: str = Field("", description="叙述时间：顺叙/倒叙/插叙/混合")
    scene_transitions: int = Field(0, description="场景转换次数")
    time_jumps: int = Field(0, description="时间跳跃次数")
    viewpoint_switches: int = Field(0, description="视角切换次数")
    event_density: int = Field(0, description="事件密度 1-5")
    info_density: int = Field(0, description="信息密度 1-5")
    time_span: str = Field("", description="时间跨度")
    space_span: str = Field("", description="空间跨度")
    scene_count: int = Field(0, description="场景数量")
    conflict_count: int = Field(0, description="冲突数量")
    suspense_score: int = Field(0, description="悬念密度 1-5")
    foreshadow_score: int = Field(0, description="伏笔密度 1-5")
    hook_score: int = Field(0, description="章节钩子强度 1-5")
    emotional_arc: str = Field("", description="情感弧线描述")
    confidence: float = Field(0, description="置信度 0-1")


class StyleResult(BaseModel):
    """风格判断。"""

    formality: int = Field(0, description="正式度 1-5")
    orality: int = Field(0, description="口语度 1-5")
    classical_ratio: float = Field(0, description="文言/白话比例 0-1")
    ai_flavor: int = Field(0, description="AI 味打分 1-5，越高越像 AI 生成")
    style_tags: List[str] = Field(
        default_factory=list, description="风格标签，如：冷峻/白描/华丽/幽默"
    )
    objectivity: float = Field(0, description="客观叙述占比 0-1")
    confidence: float = Field(0, description="置信度 0-1")


class BookResult(BaseModel):
    """全书叙事结构归纳。"""

    hero_journey_stage: str = Field("", description="英雄之旅阶段")
    act_structure: str = Field("", description="幕结构")
    main_arc: str = Field("", description="主线弧光")
    themes: List[AnyDict] = Field(
        default_factory=list, description="主题列表，每项含 name 与 weight"
    )
    motifs: List[str] = Field(default_factory=list, description="母题")
    symbols: List[str] = Field(default_factory=list, description="象征物")
    worldbuilding_density: float = Field(0, description="世界构建密度 0-1")
    target_audience: str = Field("", description="目标读者")
    confidence: float = Field(0, description="置信度 0-1")


# ──── D 档：级联 LLM 分支输出 ────


class SentimentResult(BaseModel):
    """情感分析。"""

    sentiment_mean: float = Field(0, description="情感均值 0-1，0.5 中性")
    sentiment_std: float = Field(0, description="情感波动 0-1")
    emotion_mix: Dict[str, float] = Field(
        default_factory=dict, description="情绪分布：喜/怒/哀/惧/惊/恶/欲"
    )
    irony_present: bool = Field(False, description="是否存在反讽")
    complex_emotion: str = Field("", description="复杂情绪说明")
    confidence: float = Field(0, description="置信度 0-1")


class TopicResult(BaseModel):
    """主题识别。"""

    topics: List[AnyDict] = Field(
        default_factory=list, description="主题列表，每项含 name/weight/evidence"
    )
    genre_tags: List[str] = Field(default_factory=list, description="题材标签")
    motifs: List[str] = Field(default_factory=list, description="母题")
    confidence: float = Field(0, description="置信度 0-1")


class CorefResult(BaseModel):
    """指代消解。"""

    chains: List[AnyDict] = Field(
        default_factory=list, description="指代链，每项含 entity/mentions/first_pos"
    )
    unresolved: List[Dict[str, str]] = Field(
        default_factory=list, description="未消解的代词，每项含 pronoun/context"
    )
    complexity: int = Field(0, description="指代复杂度 1-5")
    confidence: float = Field(0, description="置信度 0-1")


class ViewpointResult(BaseModel):
    """叙事视角判断。"""

    person: str = Field("", description="人称：第一/二/三人称")
    viewpoint: str = Field("", description="视角：限知/全知/客观/混合")
    perspective_entity: str = Field("", description="视角主体")
    head_hopping: bool = Field(False, description="是否存在视角跳跃")
    confidence: float = Field(0, description="置信度 0-1")


class SceneResult(BaseModel):
    """场景切分。"""

    scenes: List[AnyDict] = Field(
        default_factory=list,
        description="场景列表，每项含 start_para/end_para/location/time/chars/summary",
    )
    n_scenes: int = Field(0, description="场景数量")
    confidence: float = Field(0, description="置信度 0-1")


class DialogueResult(BaseModel):
    """对话与叙述构成。"""

    direct_dialogue_ratio: float = Field(0, description="直接引语占比 0-1")
    indirect_dialogue_ratio: float = Field(0, description="间接引语占比 0-1")
    free_indirect_ratio: float = Field(0, description="自由间接引语占比 0-1")
    narration_ratio: float = Field(0, description="叙述占比 0-1")
    description_ratio: float = Field(0, description="描写占比 0-1")
    confidence: float = Field(0, description="置信度 0-1")


class CognitiveLoadResult(BaseModel):
    """认知负荷评估。"""

    cognitive_load: int = Field(0, description="认知负荷 1-5")
    reasons: List[str] = Field(default_factory=list, description="负荷来源说明")
    suggested_reader_level: str = Field("", description="建议读者层级")
    readability_score: float = Field(0, description="可读性得分 0-100")
    confidence: float = Field(0, description="置信度 0-1")