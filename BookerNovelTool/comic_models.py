from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ──── 世界书资产（离线解构产物，运行时只读参考）────


class GameCharacter(BaseModel):
    """游戏角色卡：小说中出场人物的结构化画像。"""

    id: str = Field(..., description="角色唯一标识")
    name: str = Field(..., description="角色姓名")
    role: str = Field(..., description="角色定位：主角/配角")
    description: str = Field(..., description="角色背景与外貌简述")
    traits: List[str] = Field(default_factory=list, description="性格标签")
    relationships: List[Dict[str, str]] = Field(default_factory=list, description="关系列表，每项包含 target 与 relation")


class GameLocation(BaseModel):
    """游戏地点。"""

    id: str = Field(..., description="地点唯一标识")
    name: str = Field(..., description="地点名称")
    description: str = Field(..., description="环境细节描述")


class GameItem(BaseModel):
    """游戏物品。"""

    id: str = Field(..., description="物品唯一标识")
    name: str = Field(..., description="物品名称")
    description: str = Field(..., description="物品描述")
    location: Optional[str] = Field(None, description="初始所在地点 ID")


class SceneElement(BaseModel):
    """场景中的一个表现单元：动作、对话或转场。"""

    type: Literal["action", "dialogue", "transition"] = Field(..., description="单元类型：action/dialogue/transition")
    content: str = Field(..., description="描述内容")
    speaker: Optional[str] = Field(None, description="说话人，对话类型必填")
    lines: Optional[List[str]] = Field(None, description="台词列表")
    emotion: Optional[str] = Field(None, description="语气与情绪")


class GameScene(BaseModel):
    """一个游戏场景。"""

    scene_number: int = Field(..., description="场景序号")
    location: str = Field(..., description="场景所在地点 ID")
    characters_present: List[str] = Field(default_factory=list, description="在场角色 ID 列表")
    elements: List[SceneElement] = Field(default_factory=list, description="场景表现单元列表")


class Worldbook(BaseModel):
    """世界书：文字游戏世界的“真实”资产，由离线解构产出，运行时只读参考。"""

    characters: List[GameCharacter] = Field(default_factory=list, description="角色卡列表")
    locations: List[GameLocation] = Field(default_factory=list, description="地点列表")
    items: List[GameItem] = Field(default_factory=list, description="物品列表")
    scenes: List[GameScene] = Field(default_factory=list, description="从小说解构出的场景列表")
    rules: List[str] = Field(default_factory=list, description="世界硬规则，如“此门需要钥匙才能打开”")


class InitialGameState(BaseModel):
    """初始游戏状态。"""

    location: str = Field(..., description="起始地点 ID")
    inventory: List[str] = Field(default_factory=list, description="初始背包")
    present_characters: List[str] = Field(default_factory=list, description="初始在场角色")
    flags: Dict[str, Any] = Field(default_factory=dict, description="剧情标志")


class NovelGameAssets(BaseModel):
    """从小说解构出的全部游戏资产。"""

    worldbook: Worldbook = Field(..., description="世界书")
    initial_state: InitialGameState = Field(..., description="初始状态")


# ──── 运行时状态（世界真相的唯一权威，由 Python 维护，非 LLM 记忆）────


class GameState(BaseModel):
    """运行时游戏状态，每回合由 Python 显式更新。"""

    location: str = Field(..., description="当前地点 ID")
    inventory: List[str] = Field(default_factory=list, description="当前背包")
    present_characters: List[str] = Field(default_factory=list, description="当前在场角色")
    relationships: Dict[str, float] = Field(default_factory=dict, description="角色关系值，键为角色 ID")
    flags: Dict[str, Any] = Field(default_factory=dict, description="剧情标志")
    rolling_summary: str = Field(default="", description="滚动故事摘要")
    turn: int = Field(default=0, description="已进行回合数")


class WorldChange(BaseModel):
    """单回合 LLM 输出：叙事文本与世界变更指令。"""

    narration: str = Field(..., description="本回合叙事文本")
    scene_change: Optional[str] = Field(None, description="新地点 ID，None 表示保持当前地点")
    inventory_delta: Optional[Dict[str, List[str]]] = Field(None, description="背包变更，{add: [...], remove: [...]}")
    relationship_delta: Optional[Dict[str, float]] = Field(None, description="关系值变更，{角色 ID: 增量}")
    flags_delta: Optional[Dict[str, Any]] = Field(None, description="标志位变更")
    game_over: bool = Field(default=False, description="是否结束游戏")
