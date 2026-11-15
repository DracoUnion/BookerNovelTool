# 提示词模板。
# 渲染使用 util.render_prompt（正则替换 {占位符}），
# 因此字面量花括号需写成 {{ }}，占位符写成 {xxx}。


# ──── 阶段一：章节扫描 ────

SCAN_PMT = '''
你是一位小说章节扫描分析师。你的任务是对给定的**单章正文**进行结构化扫描，提取该章的核心信息。

## 任务

对当前章节正文进行结构化扫描，输出包含章节摘要、关键事件节点、人物动态、状态变化、情绪基调、伏笔动态、冲突烈度等信息。

## 要求

1.  `chapter_summary` 须为 50 字以内的核心摘要。
2.  `plot_node_list` 提取本章最重要的事件节点，最多 5 条，按发生顺序排列；`emotion_score` 取 -9 到 +9 的整数。
3.  `character_list` 记录本章登场的所有人物；`is_new` 标明该角色是否**本章首次登场**（本章首次登场填 `true`，已有角色填 `false`）。
4.  `character_state_change` 记录已有角色在本章的状态变化（处境/关系/认知三维，无变化维度填 `null`）。
5.  `foreshadowing_set.planted_chapter` 填当前章号（{chapter_index}）；`foreshadowing_payoff` 只报告“本章回收了之前哪章的伏笔”，其 `set_chapter` 必须 ≤ 当前章号（单章扫描看不到未来回收）。
6.  `emotional_tone`、`conflict_level`、`core_trope_usage_density` 取 0-10 的整数。
7.  `word_count` 为本章正文的近似字数（数字）。
8.  `dialogue_ratio`、`description_density` 为 0-1 的浮点数。
9.  枚举字段（如 `chapter_end_hook_type`、`situation_change` 等）从候选集中选，无法判断填 `null`。
10. P2 可选字段无法判断填 `null` 或 `[]`，不要编造。
11. **训练样本字段（可选）**：若启用训练数据生成，填写 `training_sample` 的 `instruction`、`instruction_type`、`output`、`style_label`、`content_description` 这 5 个核心字段；若不启用，输出 `"training_sample": null`。
12.  JSON 格式输出，注意输出包含在三个反引号（```）中。

## 格式

```
{{
  "module": "章节摘要",
  "chapter_index": {chapter_index},
  "chapter_title": {chapter_title},
  "chapter_summary": "50字以内摘要",
  "word_count": 0,
  "emotional_tone": 0,
  "chapter_end_hook": "...或null",
  "conflict_level": 0,
  "plot_node_list": [{{"event_description": "...", "original_quote": "...或null", "emotion_score": 0}}],
  "character_list": [{{"name": "...", "role": "...", "traits": ["..."], "is_new": false}}],
  "character_state_change": [{{"name": "...", "situation": "...或null", "relationship": "...或null", "cognition": "...或null"}}],
  "foreshadowing_set": [{{"content": "...", "planted_chapter": {chapter_index}, "hint": "...或null"}}],
  "foreshadowing_payoff": [{{"content": "...", "set_chapter": 0, "gap_chapters": 0}}],
  "core_trope_usage_density": 0,
  "chapter_end_hook_type": "...或null",
  "situation_change": "...或null",
  "relationship_change": "...或null",
  "cognition_change": "...或null",
  "emotion_direction": "...或null",
  "perceptible_change_flag": false,
  "dialogue_ratio": 0.0,
  "description_density": 0.0,
  "timeline_node": "...或null",
  "sentence_pattern_features": {{}}或null,
  "source_page_range": "...或null",
  "chapter_title_style_type": "...或null",
  "paragraph_function_tags": [{{"paragraph_range": "...", "function_type": "..."}}],
  "key_dialogue_excerpt": ["..."],
  "dialogue_iceberg_check": {{}}或null,
  "sensory_preference": ["..."],
  "training_sample": null
}}
```

## 当前章节

序号：{chapter_index}
标题：{chapter_title}

[content]
{chapter_text}
[/content]
'''


# ──── 阶段二：各模块聚合提示词 ────
# 每个模块一个完整提示词，任务说明与输出 Schema 均内联在模板中，
# 渲染时仅替换 {all_chapter_summaries}、{book_meta} 占位符。

AGGREGATE_PMT_GENRE = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"题材与定位"模块。

## 任务

你的任务是判断该书的题材标签、目标读者与市场定位，提炼其核心套路与独特卖点。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"题材与定位","genre_tags":["..."],"target_audience":"...","market_position":"...","unique_selling_point":"...","target_platform":"...或null","core_trope":"...或null"}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_TITLE = '''
你是一位小说拆解聚合架构师。基于全书章节摘要和书籍元信息，生成"书名与简介"模块。

## 任务

你的任务是评估书名的记忆点与相关性，并结合简介提炼其吸引读者的钩子与一句话卖点。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"书名与简介","title_analysis":{{"memorability":0,"relevance":0,"comment":"..."}},"blurb_hooks":["..."],"blurb_effectiveness":"...","one_sentence_pitch":"...或null"}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_WORLD = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"世界观设定"模块。

## 任务

你的任务是梳理世界观的故事核心、核心规则、阵营势力、独特设定及其逻辑自洽性。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"世界观设定","story_core":"...或null","core_theme":"...或null","core_rules":"...","factions":[{{"name":"...","desc":"...","chapters_involved":"第X-Y章"}}],"unique_elements":["..."],"logic_consistency":"...","world_immersion_score":0}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_CHARACTER = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"人物图谱"模块。

## 任务

你的任务是构建人物图谱，刻画主角弧光、配角关系与反派压力模型，并梳理人物关系图谱。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"人物图谱","protagonist":{{"name":"...","desire":"...","flaw":"...","belief":"...","arc":"从...到..."}},"supporting_chars":[{{"name":"...","role":"...","relation_evolution":"..."}}],"antagonist":{{"name":"...","pressure_model":"...","motivation":"...","final_confrontation_chapter":0}},"character_relationship_graph":{{"nodes":["..."],"edges":[{{"from":"...","to":"...","relation":"..."}}]}},"character_profile":{{}}或null,"character_arc":{{}}或null,"relationship_progression_nodes":[{{"chapter":0,"description":"..."}}],"ensemble_function_classification":{{}}或null,"dual_desire_design_validation":{{}}或null}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_STRUCTURE = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"主线与结构"模块。

## 任务

你的任务是概括主线故事，划分起承转合，梳理支线及其收束，并分析激励事件、八幕结构与反派压力升级路径。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"主线与结构","main_storyline":"...","structure":{{"acts":[{{"act":"起/承/转/合","chapters":"第X-Y章","summary":"..."}}]}},"subplots":[{{"name":"...","chapters":"...","resolution_chapter":"..."}}],"structure_score":0,"seven_step_structure_analysis":{{}}或null,"inciting_incident_analysis":"...或null","eight_act_structure_overview":[{{"act":"...","chapters":"...","summary":"..."}}],"gap_progression_mechanism":"...或null","three_layer_conflict_rule":{{}}或null,"antagonistic_force_escalation_path":"...或null"}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_RHYTHM = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"节奏与爽点"模块。

## 任务

你的任务是定位高潮爽点、分析节奏图谱与爽点周期模式，指出节奏洼地。`emotion_curve` 输出结构化列表（每章一项），反派压力升级路径见"主线与结构"模块。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"节奏与爽点","climax_points":[{{"chapter":0,"type":"...","intensity":0}}],"flat_periods":[{{"chapters":"第X-Y章","desc":"..."}}],"emotion_curve":[{{"chapter":0,"value":0}}],"rhythm_score":0,"rhythm_map":[{{"chapter":0,"type":"...","note":"..."}}],"selling_point_cycle_pattern":{{}}或null,"core_emotion_self_check_result":{{}}或null}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_GIMMICK = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"金手指/核心创意"模块。

## 任务

你的任务是提炼本书的核心创意与金手指设定，评估其创新性与执行度。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"金手指/核心创意","unique_setting":"...","innovation":"...","core_gimmick":"...","creativity_score":0,"execution_score":0}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_OPENING = '''
你是一位小说拆解聚合架构师。基于全书章节摘要（聚焦前3章），生成"开篇钩子"模块。

## 任务

你的任务是聚焦前三章，评估开篇钩子强度与黄金三章效果，提示读者流失风险。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"开篇钩子","first_500_words_hook":"...","protagonist_first_impression":"...","chapter_end_hooks":[{{"chapter":0,"hook":"...","strength":0}}],"golden_three_effectiveness":"...","drop_off_risk":"..."}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_FORESHADOW = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"伏笔与铺垫"模块。

## 任务

你的任务是盘点全书伏笔的埋设与回收，分析信息差与连续性。`foreshadowing_master_table` 汇总全书所有伏笔（含回收章号与间隔），与章节级扫描（单章看不到未来回收）分工互补。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"伏笔与铺垫","foreshadowing_list":[{{"id":1,"plant_chapter":0,"payoff_chapter":0,"description":"...","function":"...","is_resolved":true}}],"information_asymmetry":"...","continuity":"...","foreshadowing_score":0,"foreshadowing_master_table":[{{"content":"...","set_chapter":0,"payoff_chapter":0,"gap_chapters":0,"function":"..."}}],"scattered_plot_fallback_list":["..."]}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_PATTERN = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"可迁移模式"模块。

## 任务

你的任务是提炼可迁移的结构、人物、节奏与写作技法模式，并给出借鉴建议。按照给定格式以 JSON 输出，包含在三个反引号（```）中。

## 输出格式

```
{{"module":"可迁移模式","structural_patterns":["..."],"character_patterns":["..."],"rhythm_patterns":["..."],"writing_techniques":["..."],"imitation_advice":"..."}}
```

## 全书章节摘要

[content]
{all_chapter_summaries}
[/content]

## 书籍元信息

[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_STYLE = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"文风与语言"模块。

## 任务
分析叙事视角、对话技法、句式文风、语言指纹、母题意象与风格边界。按 JSON 输出，包含在三个反引号中。

## 输出格式
```
{{"module":"文风与语言","narrative_pov":"...","dialogue_technique_summary":"...","sentence_and_style_review":"...","language_fingerprint":{{"high_freq_patterns":["..."],"vocabulary_preference":"...","rhythm_note":"..."}},"motif_image_system":["..."],"style_boundary":["..."]}}
```

## 全书章节摘要
[content]
{all_chapter_summaries}
[/content]

## 书籍元信息
[content]
{book_meta}
[/content]
'''

AGGREGATE_PMT_RATING = '''
你是一位小说拆解聚合架构师。基于全书章节摘要，生成"综合评分"模块。

## 任务
对选题、结构、人物、对话、文笔、世界观、商业性七个维度各打 1-5 分，给出结构总评和一句话总结。按 JSON 输出，包含在三个反引号中。

## 输出格式
```
{{"module":"综合评分","seven_dimension_rating":{{"topic":0,"structure":0,"character":0,"dialogue":0,"writing":0,"worldbuilding":0,"commercial":0}},"structure_review":{{"strengths":["..."],"improvements":["..."]}},"one_sentence_summary":"..."}}
```

## 全书章节摘要
[content]
{all_chapter_summaries}
[/content]

## 书籍元信息
[content]
{book_meta}
[/content]
'''

AGGREGATE_PROMPT_MAP = {
    "题材与定位": AGGREGATE_PMT_GENRE,
    "书名与简介": AGGREGATE_PMT_TITLE,
    "世界观设定": AGGREGATE_PMT_WORLD,
    "人物图谱": AGGREGATE_PMT_CHARACTER,
    "主线与结构": AGGREGATE_PMT_STRUCTURE,
    "节奏与爽点": AGGREGATE_PMT_RHYTHM,
    "金手指/核心创意": AGGREGATE_PMT_GIMMICK,
    "开篇钩子": AGGREGATE_PMT_OPENING,
    "伏笔与铺垫": AGGREGATE_PMT_FORESHADOW,
    "可迁移模式": AGGREGATE_PMT_PATTERN,
    "文风与语言": AGGREGATE_PMT_STYLE,
    "综合评分": AGGREGATE_PMT_RATING,
}


# 系统提示词
SCAN_SYSTEM = "你是一位小说章节扫描分析师。你只对单章正文做结构化扫描，并以 JSON 形式输出，输出包含在三个反引号（```）中。"
AGGREGATE_SYSTEM = "你是一位小说拆解聚合架构师。你基于全书章节摘要生成单一分析模块，并以 JSON 形式输出，输出包含在三个反引号（```）中。"
