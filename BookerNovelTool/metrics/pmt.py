#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""C 档（必须 LLM）提示词模板。

渲染使用 `BookerNovelTool.util.render_prompt`（正则替换 {占位符}），
因此字面量花括号无需转义，JSON 大纲直接写单括号；只有 {text}/{summaries}
等占位符会被替换。
"""

# 统一的系统提示：只输出 JSON，不解释，不新增原文没有的信息。
METRICS_SYSTEM = "你是一位严谨的小说文本分析助手。只输出 JSON，不要解释，不要新增原文中没有的信息。"

RHETORIC_PMT = '''
你是一位修辞学分析师。请识别以下小说片段中确实出现的修辞手法。

## 要求

1.  统计以下修辞的出现次数：明喻、暗喻/隐喻、拟人、夸张、排比、反复、反讽/讽刺、双关、象征、通感。
2.  `examples` 给出 1-5 个最有代表性的实例，每项含 `type`（修辞类型）与 `text`（原文摘录）。
3.  `rhetoric_density` 是修辞出现次数与总句数的比值（0-1）。
4.  `confidence` 是本次判断的置信度（0-1）。

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
  "rhetoric_density": 0,
  "confidence": 0
}
```

## 小说片段

[content]
{text}
[/content]
'''

DESCRIPTION_PMT = '''
你是一位文本分析专家。请按句对以下小说片段进行分类，统计各类描写/叙述的句数与比例。

## 要求

1.  `counts` 中：`psych` 心理描写、`action` 动作描写、`environment` 环境描写、`dialogue` 人物对话、`narration` 纯叙述。
2.  一句话可归属多类时，按最主要的一类计；拿不准的归入 `narration`。
3.  `ratios` 为各类型句数占总句数的比例（0-1，合计约等于 1）。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "counts": {"psych": 0, "action": 0, "environment": 0, "dialogue": 0, "narration": 0},
  "ratios": {"psych": 0, "action": 0, "environment": 0, "dialogue": 0, "narration": 0},
  "confidence": 0
}
```

## 小说片段

[content]
{text}
[/content]
'''

NARRATIVE_PMT = '''
你是一位叙事学分析师。请分析以下小说片段的叙事学特征。

## 要求

1.  `person`：整体人称（第一/二/三人称）。
2.  `viewpoint`：叙事视角（限知/全知/客观/混合）。
3.  `perspective_entity`：视角主体（站在谁的位置叙述）。
4.  `narration_time`：叙述时间处理（顺叙/倒叙/插叙/混合）。
5.  `scene_transitions`/`time_jumps`/`viewpoint_switches`：场景转换、时间跳跃、视角切换次数。
6.  `event_density`/`info_density`：事件密度与信息密度（1-5）。
7.  `time_span`/`space_span`：时间跨度与空间跨度。
8.  `scene_count`/`conflict_count`：场景数量与冲突数量。
9.  `suspense_score`/`foreshadow_score`/`hook_score`：悬念、伏笔、钩子强度（1-5）。
10. `emotional_arc`：情感弧线的一句话描述。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "person": "第三人称",
  "viewpoint": "全知",
  "perspective_entity": "",
  "narration_time": "顺叙",
  "scene_transitions": 0,
  "time_jumps": 0,
  "viewpoint_switches": 0,
  "event_density": 3,
  "info_density": 3,
  "time_span": "",
  "space_span": "",
  "scene_count": 0,
  "conflict_count": 0,
  "suspense_score": 3,
  "foreshadow_score": 3,
  "hook_score": 3,
  "emotional_arc": "",
  "confidence": 0
}
```

## 小说片段

[content]
{text}
[/content]
'''

STYLE_PMT = '''
你是一位文学风格分析师。请评估以下小说片段的风格特征。

## 要求

1.  `formality`（1-5，越大越书面）、`orality`（1-5，越大越口语）。
2.  `classical_ratio`：文言/文雅表达占全文比例（0-1）。
3.  `ai_flavor`：AI 生成痕迹打分（1-5，越大越像 AI 写的：排比滥用、总结腔、万能词堆砌等）。
4.  `style_tags`：2-6 个风格标签，如：冷峻/白描/华丽/幽默/华丽/幽默/啰嗦/紧凑。
5.  `objectivity`：客观叙述占比（0-1，越大越少主观心理描写）。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "formality": 3,
  "orality": 3,
  "classical_ratio": 0,
  "ai_flavor": 2,
  "style_tags": ["白描", "紧凑"],
  "objectivity": 0.5,
  "confidence": 0
}
```

## 小说片段

[content]
{text}
[/content]
'''

BOOK_PMT = '''
你是一位资深小说编辑。以下是某本小说各章的简介/摘要，请归纳全书叙事结构。

## 要求

1.  `hero_journey_stage`：全书处于英雄之旅模型的哪个阶段。
2.  `act_structure`：幕结构（三幕/四幕/五幕等）。
3.  `main_arc`：主线弧光的一句话概括。
4.  `themes`：2-5 个主题，每项含 `name` 与 `weight`（0-1，越大越重要）。
5.  `motifs`/`symbols`：反复出现的母题与象征物。
6.  `worldbuilding_density`：世界构建/设定展开密度（0-1）。
7.  `target_audience`：目标读者画像。

## 输出格式

把结果 JSON 包裹在三个反引号（\`\`\`）中：

```
{
  "hero_journey_stage": "",
  "act_structure": "",
  "main_arc": "",
  "themes": [{"name": "", "weight": 0.5}],
  "motifs": [],
  "symbols": [],
  "worldbuilding_density": 0.5,
  "target_audience": "",
  "confidence": 0
}
```

## 章节摘要

[content]
{summaries}
[/content]
'''