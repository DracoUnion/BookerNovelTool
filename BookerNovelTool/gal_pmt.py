# -*- coding: utf-8 -*-
"""gal 子命令提示词常量。

所有模板为全局多行字符串常量，命名 `{XXX}_PMT`，使用 `{...}` 占位符，
尽量减少字符串拼接；所有提示词为中文；输出为 JSON 的模板强调使用
三个反引号包裹（```json ... ```）。
"""

# ── 离线解构：角色卡 ──────────────────────────────────────────

PMT_EXTRACT_CHARACTERS = """你是小说解构专家，任务是从以下章节文本中抽取全部出场角色，输出结构化角色卡列表。

【抽取要求】
1. 决不遗漏：章节中出现过名字、外貌描写、台词或动作的角色都必须抽取，哪怕只出现一次。
2. 每个角色输出一条：id（按本章出现顺序编为 char_001、char_002…）、name、role（protagonist/supporting/antagonist/npc）、description、traits（性格标签）、voice（2-3 句该角色的原文台词，必须引用原文，不可凭空编造）、knowledge_scope（该角色“可能知道”的信息标签列表）、relationships（与其他角色的关系：target_id、relation 如 TRUSTS/FEARs/ALLY_OF/OPPOSES/WORKS_FOR、strength -1~1）。
3. 仅基于本章文本，不要引入外部知识。

【章节文本】
{chapter_text}

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "characters": [
    {
      "id": "char_001",
      "name": "...",
      "role": "protagonist",
      "description": "...",
      "traits": ["..."],
      "voice": "...",
      "knowledge_scope": ["..."],
      "relationships": [{"target_id": "...", "relation": "...", "strength": 0.0}]
    }
  ]
}
```
"""

# ── 离线解构：场景列表（强完整性规则，对抗 LLM 摘要倾向）──────────────────────────────────────────

PMT_EXTRACT_SCENES = """你是小说解构专家，任务是将以下章节文本拆分为完整的场景列表，输出结构化数据。

【强完整性规则（必须严格遵守）】
1. 决不遗漏任何情节：章节中的每一段对话、每一个动作片段都必须落到某个场景中，禁止将大段情节压缩成单个概括性场景。
2. 每一段对话 = 至少一个场景：同一连续对话段落必须作为独立场景（type 为 dialogue 的元素）。
3. 场景密度下限：每 3000 字正文至少产出 4 个场景；情节密集的章节应更多。
4. 闪回不压缩：is_flashback=true 的场景必须完整展开全部细节，不可概括。
5. 场景划分依据：地点变更、时间跳跃、人物进出、对话开始/结束，均应切分为新场景。
6. 每个场景输出：scene_number（按顺序编号）、chapter（章号）、location_id（所在地点 ID，未出现新地点时沿用前一地点）、characters_present（在场角色 ID 列表）、elements（action/dialogue/transition/reveal 元素列表，每元素含 type、content、speaker_id、emotion）、is_flashback。

【章节文本】
{chapter_text}

【自检（输出前必须在心里完成）】
- 是否有对话段落没被独立成场景？有则补全。
- 是否有大段情节被概括成一个场景？有则拆分。
- 本章 3000 字是否至少 4 个场景？不足则继续拆分。

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "scenes": [
    {
      "scene_number": 1,
      "chapter": 1,
      "location_id": "loc_001",
      "characters_present": ["char_001"],
      "elements": [
        {"type": "action", "content": "...", "speaker_id": null, "emotion": null},
        {"type": "dialogue", "content": "...", "speaker_id": "char_001", "emotion": "惊讶"}
      ],
      "is_flashback": false
    }
  ]
}
```
"""

# ── 离线解构：地点与连接 ──────────────────────────────────────

PMT_EXTRACT_LOCATIONS = """你是小说解构专家，任务是从以下章节文本中抽取全部地点及其连接关系。

【抽取要求】
1. 决不遗漏：文本中提及的所有场景发生地点都必须抽取。
2. 每个地点输出：id（loc_001…）、name、description（环境细节）、connections（可达地点 ID 列表，依据文本中的移动描写推断）、items（初始位于该地点的物品标识列表）。
3. 仅基于本章文本，不要引入外部知识。

【章节文本】
{chapter_text}

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "locations": [
    {
      "id": "loc_001",
      "name": "...",
      "description": "...",
      "connections": ["loc_002"],
      "items": ["..."]
    }
  ]
}
```
"""

# ── 跨章实体合并 ─────────────────────────────────────────────

PMT_MERGE_ENTITIES = """你是小说世界书编辑，任务是把多章抽取出的角色卡与地点卡合并去重，产出统一的世界书。

【合并规则】
1. 角色去重：同名角色（或明显为同一人的不同称呼）合并为一张卡，保留 id 为第一次出现的 id，name 以最常用名称为准，description 取最详尽版本，traits 取并集，voice 保留第一条原文台词样本，knowledge_scope 取并集，relationships 取并集并去重。
2. 地点去重：同名地点合并，connections 取并集，items 取并集。
3. 从全书文本中进一步提取世界硬规则（rules，如“此门需钥匙”）与势力（factions），每条规则一句简短中文。
4. 所有 id 统一重编：角色 char_001…，地点 loc_001…，场景中的 characters_present/location_id 引用新 id。

【输入】
全书文本：{full_text}
各章角色卡 JSON：{chapter_characters}
各章地点卡 JSON：{chapter_locations}

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "title": "...",
  "characters": [...],
  "locations": [...],
  "rules": ["..."],
  "factions": ["..."]
}
```
"""

# ── 运行时：导演（单回合叙事与变更建议）───────────────────────

PMT_RUNTIME_DIRECTOR = """你是文字游戏导演兼所有角色的配音演员。根据当前世界状态与玩家输入，输出本回合的叙事与世界变更建议。

【核心约束】
1. 角色知识边界：每个角色只知其 knowledge_scope 覆盖的信息，台词与行为不得超出该范围。
2. 台词风格：每个角色台词须符合其 voice 样本的语气与说话方式。
3. 最小变化：本回合世界变化应尽可能小，只在必要时设置 scene_change；scene_change 仅在玩家显式移动时才可设置，保持原地则为 null。
4. 对话：本回合出场角色的台词应放入 dialogue 列表，每项含 speaker_id、line、emotion。
5. 状态变更：item_delta（{"add": [...], "remove": [...]}）、relationship_delta（[{"char_id":..., "delta":...}]，delta 在 -1~1 之间）、flag_update 均仅作为建议，由程序另行校验。
6. 只输出一个 JSON 对象，不要任何额外文本、不要 markdown 代码块以外的说明。

【世界书】
{worldbook}

【当前状态】
{state}

【滚动摘要】
{rolling_summary}

【最近历史（逐字）】
{recent_history}

【玩家输入】
{player_input}

【上一回合校验反馈】
{validation_feedback}

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "narration": "...",
  "dialogue": [{"speaker_id": "...", "line": "...", "emotion": "..."}],
  "scene_change": null,
  "item_delta": {"add": [], "remove": []},
  "relationship_delta": [{"char_id": "...", "delta": 0.1}],
  "flag_update": {},
  "game_over": false
}
```
"""

# ── 运行时：滚动摘要压缩 ─────────────────────────────────────

PMT_RUNTIME_SUMMARY = """你是故事编辑，任务是将旧滚动摘要与新增历史压缩为 1-3 句的累积摘要，用于后续回合的上下文。

【输入】
旧滚动摘要：{rolling_summary}
新增历史：{history}

【要求】
1. 保留关键剧情节点、当前地点、在场角色、背包物品、重要标志与关系变化。
2. 输出 1-3 句中文，不要额外说明。

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "summary": "..."
}
```
"""


# ── 运行时：硬规则裁判（补充 Python 侧 engine.apply()）───────

PMT_VALIDATE_CHANGE = """你是文字游戏规则裁判。根据世界书与当前状态，判定本回合 LLM 输出的世界变更建议是否合规。

【判定规则】
1. scene_change：目标地点 ID 必须存在于世界书地点列表，否则不合规。
2. item_delta add：物品必须位于当前地点 items 或玩家背包中，否则不合规。
3. item_delta remove：物品必须在玩家背包中，否则不合规。
4. relationship_delta：char_id 必须存在于世界书角色卡，delta 裁剪到 [-1, 1]；超出应裁剪后再判定。
5. flag_update：键值对形式，无强制限制。
6. 任何字段若指向不存在的实体，直接判定不合规并给出失败原因与修复要点。

【世界书】
{worldbook}

【当前状态】
{state}

【本回合变更建议】
{change}

【输出】
只输出一个 JSON 对象，不要任何额外文本，格式：
```json
{
  "valid": true,
  "reason": null,
  "fixes": []
}
```
"""
