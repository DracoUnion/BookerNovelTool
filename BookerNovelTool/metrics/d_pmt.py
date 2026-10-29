#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""D 档（规则 + LLM 级联）提示词模板。

规则结果低置信度时才触发 LLM 分支；JSON 输出用三个反引号包裹。
"""

D_SENTIMENT_PMT = '''
你是一位情感分析师。请分析以下小说片段的情感特征。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "sentiment_mean": 0.5,
  "sentiment_std": 0.3,
  "emotion_mix": {"喜": 0.5, "怒": 0.2, "哀": 0.1, "惧": 0.1, "惊": 0.05, "恶": 0.05, "欲": 0.0},
  "irony_present": false,
  "complex_emotion": "",
  "confidence": 0.8
}
```

## 说明

- `sentiment_mean`：0-1，0.5 为中性，越大越正面。
- `emotion_mix`：七种基本情绪占比，合计约 1。
- `irony_present`：是否使用了反讽。
- `confidence`：置信度 0-1。

## 小说片段

[content]
{text}
[/content]
'''

D_TOPIC_PMT = '''
你是一位主题分析师。请识别以下小说片段的主题与母题。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "topics": [{"name": "复仇", "weight": 0.8, "evidence": "原文线索"}],
  "genre_tags": ["都市", "复仇"],
  "motifs": ["戒指", "雨"],
  "confidence": 0.8
}
```

## 说明

- `topics`：每个主题含 `name`/`weight`（0-1 重要性）/`evidence`（原文证据）。
- `genre_tags`：题材标签。
- `motifs`：反复出现的母题（意象/物件）。

## 小说片段

[content]
{text}
[/content]
'''

D_RHETORIC_PMT = '''
你是一位修辞学分析师。请识别以下小说片段中确实出现的修辞手法。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "simile": 0,
  "metaphor": 0,
  "personification": 0,
  "exaggeration": 0,
  "parallelism": 0,
  "repetition": 0,
  "irony": 0,
  "pun": 0,
  "symbolism": 0,
  "synaesthesia": 0,
  "examples": [{"type": "明喻", "text": "原文摘录"}],
  "rhetoric_density": 0.1,
  "confidence": 0.8
}
```

## 小说片段

[content]
{text}
[/content]
'''

D_COREF_PMT = '''
你是一位指代消解专家。请分析以下小说片段的指代关系。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "chains": [{"entity": "张三", "mentions": ["他", "张三", "那人"], "first_pos": 0}],
  "unresolved": [{"pronoun": "他", "context": "他快步走了过去"}],
  "complexity": 2,
  "confidence": 0.8
}
```

## 说明

- `chains`：指代链，`entity` 实体名，`mentions` 提及列表，`first_pos` 首次出现位置。
- `unresolved`：无法确认指向的代词。
- `complexity`：指代复杂度 1-5。

## 小说片段

[content]
{text}
[/content]
'''

D_VIEWPOINT_PMT = '''
你是一位叙事学分析师。请判断以下小说片段的叙事视角。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "person": "第三人称",
  "viewpoint": "限知",
  "perspective_entity": "张三",
  "head_hopping": false,
  "confidence": 0.8
}
```

## 说明

- `person`：第一/二/三人称。
- `viewpoint`：限知/全知/客观/混合。
- `perspective_entity`：视角主体。
- `head_hopping`：是否存在视角跳跃（一会儿写 A 心理一会儿写 B 心理）。

## 小说片段

[content]
{text}
[/content]
'''

D_SCENE_PMT = '''
你是一位场景分析师。请把以下编号段落划分为若干场景。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "scenes": [
    {"start_para": 0, "end_para": 3, "location": "街道", "time": "夜晚", "chars": ["张三"], "summary": "张三被追"},
    {"start_para": 4, "end_para": 9, "location": "茶馆", "time": "次日", "chars": ["张三", "李四"], "summary": "密谋复仇"}
  ],
  "n_scenes": 2,
  "confidence": 0.8
}
```

## 说明

场景切换的标志：时间跳跃、地点变化、人物进出、叙事段落完整收束。
`start_para`/`end_para` 为段落编号（从 0 开始）。

## 编号段落

[content]
{text}
[/content]
'''

D_DIALOGUE_PMT = '''
你是一位叙事构成分析师。请分析以下小说片段中对话、叙述与描写的构成比例。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "direct_dialogue_ratio": 0.4,
  "indirect_dialogue_ratio": 0.1,
  "free_indirect_ratio": 0.05,
  "narration_ratio": 0.35,
  "description_ratio": 0.1,
  "confidence": 0.8
}
```

## 说明

- `direct_dialogue_ratio`：直接引语占比。
- `indirect_dialogue_ratio`：间接引语占比。
- `free_indirect_ratio`：自由间接引语占比。
- `narration_ratio`：叙述占比。
- `description_ratio`：场景/外貌等描写占比。
- 各项合计约等于 1。

## 小说片段

[content]
{text}
[/content]
'''

D_DESCRIPTION_PMT = '''
你是一位描写类型分析师。请按句对以下小说片段分类，统计描写类型分布。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "counts": {"psych": 0, "action": 0, "environment": 0, "dialogue": 0, "narration": 0},
  "ratios": {"psych": 0.2, "action": 0.4, "environment": 0.1, "dialogue": 0.2, "narration": 0.1},
  "confidence": 0.8
}
```

## 小说片段

[content]
{text}
[/content]
'''

D_READABILITY_PMT = '''
你是一位可读性专家。请评估以下小说片段的认知负荷与读者友好度。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "cognitive_load": 3,
  "reasons": ["句子过长", "术语密集"],
  "suggested_reader_level": "中学生",
  "readability_score": 60,
  "confidence": 0.8
}
```

## 说明

- `cognitive_load`：认知负荷 1-5，越大越难读。
- `suggested_reader_level`：建议读者水平。
- `readability_score`：可读性得分 0-100。

## 小说片段

[content]
{text}
[/content]
'''