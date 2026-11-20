# -*- coding: utf-8 -*-
"""gal 子命令 Pydantic 模型：离线资产、运行时状态与存档结构。

所有字段均带字符描述 `Field(..., description='...')`，供提示词渲染与
人工审计参考。
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ──── 离线资产（gal-parse 产出，运行时只读）────


class Relationship(BaseModel):
    """角色之间的关系边。"""

    target_id: str = Field(..., description="关系目标角色 ID")
    relation: str = Field(..., description="关系类型，如 TRUSTS / FEARS / ALLY_OF / OPPOSES / WORKS_FOR")
    strength: float = Field(..., description="关系强度，取值范围 [-1, 1]")


class CharacterCard(BaseModel):
    """角色卡：小说中人物的结构化画像，运行时用于组装角色上下文与台词约束。"""

    id: str = Field(..., description="角色唯一标识，如 char_001")
    name: str = Field(..., description="角色姓名")
    role: Literal["protagonist", "supporting", "antagonist", "npc"] = Field(..., description="角色定位：主角/配角/反派/NPC")
    description: str = Field(..., description="角色背景与外貌简述")
    traits: List[str] = Field(default_factory=list, description="性格标签")
    voice: str = Field(..., description="说话风格样本（2-3 句原文台词，供运行时台词风格对齐）")
    knowledge_scope: List[str] = Field(default_factory=list, description="该角色“可能知道”的信息标签，运行时限制角色只知此范围内的信息")
    relationships: List[Relationship] = Field(default_factory=list, description="与其他角色的关系列表")


class Location(BaseModel):
    """游戏地点：场景发生地与物品初始所在地。"""

    id: str = Field(..., description="地点唯一标识，如 loc_001")
    name: str = Field(..., description="地点名称")
    description: str = Field(..., description="环境细节描述")
    connections: List[str] = Field(default_factory=list, description="可达地点 ID 列表，scene_change 的合法目标")
    items: List[str] = Field(default_factory=list, description="初始位于该地点的物品标识列表")


class SceneElement(BaseModel):
    """场景中的一个表现单元：动作、对话、转场或揭秘。"""

    type: Literal["action", "dialogue", "transition", "reveal"] = Field(..., description="单元类型：action/dialogue/transition/reveal")
    content: str = Field(..., description="描述内容或台词正文")
    speaker_id: Optional[str] = Field(None, description="说话人角色 ID，对话类型建议填写")
    emotion: Optional[str] = Field(None, description="语气与情绪")


class Scene(BaseModel):
    """一个游戏场景。"""

    scene_number: int = Field(..., description="场景序号")
    chapter: int = Field(..., description="所属章号")
    location_id: str = Field(..., description="场景所在地点 ID")
    characters_present: List[str] = Field(default_factory=list, description="在场角色 ID 列表")
    elements: List[SceneElement] = Field(default_factory=list, description="场景表现单元列表")
    is_flashback: bool = Field(False, description="是否为闪回场景，闪回场景运行时不得压缩叙事")


class WorldBook(BaseModel):
    """世界书：文字游戏世界的“真实”资产，由离线解构产出，运行时只读参考。"""

    title: str = Field(..., description="小说标题")
    source_hash: str = Field(..., description="小说文本 md5 指纹，用于缓存失效与存档版本校验")
    characters: List[CharacterCard] = Field(default_factory=list, description="角色卡列表")
    locations: List[Location] = Field(default_factory=list, description="地点列表")
    rules: List[str] = Field(default_factory=list, description="世界硬规则，如“此门需钥匙”")
    factions: List[str] = Field(default_factory=list, description="势力列表")


# ──── 运行时状态（世界真相的唯一权威，由 Python 状态机维护，非 LLM 记忆）────


class GameState(BaseModel):
    """运行时游戏状态，每回合由 Python 显式更新，LLM 只提出变更建议。"""

    player_location: str = Field(..., description="当前地点 ID")
    inventory: List[str] = Field(default_factory=list, description="当前背包物品标识列表")
    flags: Dict[str, Any] = Field(default_factory=dict, description="剧情标志")
    relationships: Dict[str, float] = Field(default_factory=dict, description="角色关系值，键为角色 ID，取值裁剪到 [-1, 1]")
    turn: int = Field(0, description="已进行回合数")
    rolling_summary: str = Field("", description="滚动故事摘要，始终全量进入上下文")
    present_characters: List[str] = Field(default_factory=list, description="当前在场角色 ID 列表")
    game_over: bool = Field(False, description="游戏是否结束")


class TurnResult(BaseModel):
    """单回合 LLM 输出：面向玩家的叙事与世界变更建议，由 engine 校验后应用。"""

    narration: str = Field(..., description="面向玩家的叙事文本")
    dialogue: List[dict] = Field(default_factory=list, description='[{"speaker_id":..., "line":..., "emotion":...}]')
    scene_change: Optional[str] = Field(None, description="新地点 ID，None 表示保持当前地点，仅在玩家显式移动时设置")
    item_delta: Optional[dict] = Field(None, description='{"add": [...], "remove": [...]}')
    relationship_delta: Optional[List[dict]] = Field(None, description='[{"char_id":..., "delta":...}]')
    flag_update: Optional[dict] = Field(None, description="剧情标志更新")
    game_over: bool = Field(False, description="是否结束游戏")


class SummaryResult(BaseModel):
    """滚动摘要压缩结果。"""

    summary: str = Field(..., description="1-3 句累积摘要")


class AssetsBundle(BaseModel):
    """离线解构产出的全部游戏资产。"""

    worldbook: WorldBook = Field(..., description="世界书")
    scenes: List[Scene] = Field(..., description="场景列表")
    initial_state: GameState = Field(..., description="初始游戏状态")


class SaveFile(BaseModel):
    """存档文件：运行时状态 + 最近历史窗口 + 资产包版本校验。"""

    state: GameState = Field(..., description="运行时状态")
    history_window: List[str] = Field(default_factory=list, description="最近 K 轮逐字历史")
    assets_hash: str = Field(..., description="资产包 manifest 哈希，读档时与 manifest 校验版本一致")
