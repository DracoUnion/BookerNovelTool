# 提示词模板。
# 渲染使用 util.render_prompt（正则替换 {占位符}），
# 因此字面量花括号需写成 {{ }}，占位符写成 {xxx}。
# 所有输出要求 JSON 包含在三个反引号中。
# 以下模板均使用中文。


# ──── 候选池常量 ────

EMOTION_MODULE_POOL = [
    "退婚流", "扮猪吃虎", "打脸", "追妻火葬场", "废柴逆袭", "隐藏大佬",
    "对照组反派", "误会流", "身份反转", "绝境翻盘",
]

RHYTHM_PATTERN_POOL = [
    "快节奏开局", "慢热铺垫", "三章一小爽", "十章一大爽", "双线并行", "单元剧结构",
]

CONFLICT_TYPE_POOL = [
    "身份冲突", "资源冲突", "情感冲突", "认知冲突", "阵营冲突", "代际冲突",
]

CHARACTER_ARCHETYPE_POOL = [
    "废柴逆袭", "隐藏大佬", "对照组反派", "忠犬配角", "疯批反派", "成长型主角",
]

APPLICABLE_SCENE_POOL = ["开篇", "升级段", "转折段", "收尾段", "高潮段"]

STYLE_POOL = ["冷峻克制", "华丽铺陈", "对话驱动", "白描短句", "幽默轻快", "沉重压抑"]


# ──── 系统提示词 ────

TAG_EXTRACT_SYSTEM = "你是一位跨书素材库标签专家。你从单书拆解结果中提取可比标签与变体实例，以 JSON 输出，包含在三个反引号中。"
PATTERN_CARD_SYSTEM = "你是一位跨书模式归纳专家。你基于同一标签下的多书变体，归纳可复用的模式卡片，以 JSON 输出，包含在三个反引号中。"
LINEAGE_SYSTEM = "你是一位模式谱系分析专家。你分析模式卡片之间的演化、冲突与互补关系，以 JSON 输出，包含在三个反引号中。"
MATRIX_SYSTEM = "你是一位跨书对比分析专家。你生成多维度对比矩阵，以 JSON 输出，包含在三个反引号中。"
RECOMMENDATION_SYSTEM = "你是一位网文写作顾问。你基于跨书模式库给出复用建议，以 JSON 输出，包含在三个反引号中。"


# ──── 阶段二：单书标签提取 ────

TAG_EXTRACT_PMT = '''
你是一位跨书素材库标签专家。请从给定的单书拆解结果中提取可比标签与变体实例，输出 JSON，包含在三个反引号（```）中。

## 输入数据（单书拆解结果）

[content]
{book_meta}
{chapter_summaries}
{modules}
[/content]

## 候选池

情绪模块标签：{emotion_module_pool}
节奏模式标签：{rhythm_pattern_pool}
冲突类型标签：{conflict_type_pool}
人物原型标签：{character_archetype_pool}
文风标签：{style_pool}
适用场景标签：{applicable_scene_pool}

## 要求

1. 每个标签字段从对应候选池中选择，可多选；无法判断的字段填 null 或 []。
2. `emotion_module_instances` 每条含 tag、description（非原文描述）、position、setup_chapters、payoff_chapter、aftermath_chapters；description 须具体写法，不写抽象评价。
3. `position` 取值："opening"、"first_quarter"、"middle"、"last_quarter"、"closing"。
4. 题材字段（genre_tags、subgenre_tags、target_audience、target_platform、style_label、applicable_scene_tags）尽量从书元信息与模块中判断，无法判断填 null 或 []。
5. transferability_score、prerequisite_setup、failure_modes 若无法判断填 null 或 []。
6. 最终输出一个 JSON 对象，字段与 CrossBookComparableFields 一致。

## 输出格式

```
{{
  "source_book_id": "...",
  "source_book_title": "...",
  "source_author": "...或null",
  "source_edition": "...或null",
  "genre_tags": ["..."],
  "subgenre_tags": ["..."],
  "target_audience": "...或null",
  "target_platform": "...或null",
  "emotion_module_tags": ["..."],
  "rhythm_pattern_tags": ["..."],
  "conflict_type_tags": ["..."],
  "character_archetype_tags": ["..."],
  "style_label": "...或null",
  "applicable_scene_tags": ["..."],
  "climax_interval_distribution": null或{{}},
  "setup_payoff_ratio": 0或null,
  "dialogue_description_ratio": 0.0或null,
  "sentence_rhythm_profile": null或{{}},
  "sensory_bias": ["..."],
  "opening_type": "...或null",
  "structure_model": "...或null",
  "pov_type": "...或null",
  "emotion_module_instances": [
    {{"tag": "...", "description": "...", "position": "opening", "setup_chapters": 0, "payoff_chapter": 0, "aftermath_chapters": 0}}
  ],
  "transferability_score": 0或null,
  "prerequisite_setup": ["..."],
  "failure_modes": ["..."]
}}
```
'''


# ──── 阶段三：模式卡片生成 ────

PATTERN_CARD_PMT = '''
你是一位跨书模式归纳专家。基于同一标签下的多书变体，归纳一张可复用的模式卡片，输出 JSON，包含在三个反引号（```）中。

## 标签维度：{tag_dimension}
## 标签值：{tag_value}

## 变体实例列表

[content]
{variants}
[/content]

## 要求

1. `pattern_definition` 四个子字段（trigger、emotion_engine、payoff_mode、aftermath_handling）必须具体，不能空泛。
2. `stable_elements` 是所有变体共有的结构；`variable_elements` 是变体间可替换的参数；两者均不能为空列表。
3. `variant_axis` 列出变体之间的差异维度（如“释放时机”“反派强度”）。
4. `failure_modes` 从变体描述中归纳“用砸的典型方式”，若无则填 []。
5. `variant_count` 等于变体列表长度。
6. 最终输出一个 JSON 对象，字段与 PatternCard 一致。

## 输出格式

```
{{
  "pattern_card_id": "...",
  "pattern_name": "...",
  "tag_dimension": "{tag_dimension}",
  "tag_value": "{tag_value}",
  "pattern_definition": {{
    "trigger": "...",
    "emotion_engine": "...",
    "payoff_mode": "...",
    "aftermath_handling": "..."
  }},
  "pattern_variants": [
    {{"variant_id": "...", "source_book_id": "...", "source_chapter_index": 0, "description": "...", "distinguishing_feature": "...", "effectiveness_note": "...或null"}}
  ],
  "variant_count": 0,
  "variant_axis": ["..."],
  "stable_elements": ["..."],
  "variable_elements": ["..."],
  "effectiveness_distribution": null或{{}},
  "failure_modes": ["..."]
}}
```
'''


# ──── 阶段四：模式谱系 ────

LINEAGE_PMT = '''
你是一位模式谱系分析专家。分析模式卡片之间的演化、冲突与互补关系，只输出确实存在的配对，不强行凑关系，输出 JSON，包含在三个反引号（```）中。

## 模式卡片列表（精简）

[content]
{cards}
[/content]

## 要求

1. relation_type 取值："derives"（演化）、"variant_of"（变体）、"conflicts"（冲突）、"complements"（互补）。
2. 只有确有演化/冲突/互补关系的配对才输出；缺乏依据时输出 []。
3. lineage_id 为唯一标识，parent_pattern_id 与 child_pattern_id 引用模式卡片的 pattern_card_id。
4. 最终输出一个 JSON 对象数组，每条字段与 PatternLineage 一致。

## 输出格式

```
[
  {{"lineage_id": "...", "parent_pattern_id": "...", "child_pattern_ids": ["..."], "relation_type": "derives", "note": "...或null"}}
]
```
'''


# ──── 阶段四：对比矩阵 ────

COMPARISON_MATRIX_PMT = '''
你是一位跨书对比分析专家。基于全部书籍的可比字段，生成多维度对比矩阵，输出 JSON，包含在三个反引号（```）中。

## 输入字段

[content]
{fields}
[/content]

## 要求

1. 覆盖至少以下维度：节奏密度、铺垫效率、对话占比、开篇类型分布、结构模型分布。
2. 每个维度输出 dimension、entries（各书条目）、dimension_ranking（按该维度排序的书籍 ID）。
3. entries 中每条应含 source_book_id 与该维度的数值或标签值。
4. 最终输出一个 JSON 对象数组，每条字段与 ComparisonMatrix 一致。

## 输出格式

```
[
  {{
    "dimension": "...",
    "entries": [{{"source_book_id": "...", "value": "..."}}],
    "dimension_ranking": ["...", "..."]
  }}
]
```
'''


# ──── 阶段四：复用建议 ────

REUSE_RECOMMENDATION_PMT = '''
你是一位网文写作顾问。基于跨书模式卡片与对比矩阵，给出按“写新书的场景”组织的复用建议，输出 JSON，包含在三个反引号（```）中。

## 模式卡片列表（精简）

[content]
{cards}
[/content]

## 对比矩阵

[content]
{matrix}
[/content]

## 要求

1. 按写新书场景组织：开篇、升级段、转折段、收尾段。
2. recommended_pattern_ids 与 reference_variant_ids 引用模式卡片 ID 与变体 ID。
3. avoid_failure_modes 列出该场景下应避免的失效模式。
4. adaptation_notes 给出具体改编备注。
5. 最终输出一个 JSON 对象数组，每条字段与 ReuseRecommendation 一致。

## 输出格式

```
[
  {{
    "scenario": "...",
    "recommended_pattern_ids": ["..."],
    "reference_variant_ids": ["..."],
    "avoid_failure_modes": ["..."],
    "adaptation_notes": "...或null"
  }}
]
```
'''