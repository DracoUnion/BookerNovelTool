# 历史记录

v2026.10.29

+   新增 `metrics` 子命令与 `BookerNovelTool.metrics` 子模块：小说风格/质量评价指标（A/B/C/D 四档）
+   A 档纯规则：长度/标点/词汇丰富度/信息论/句型/语音
+   B 档传统 NLP：词性/词典/主题网络/可读性/相似度/衔接连贯
+   C 档必须 LLM：修辞/描写/叙事学/风格/全书结构
+   D 档规则 + LLM 级联：情感/主题/修辞/指代/视角/场景/对话比/描写/认知负荷/相似度
+   LLM 调用复用 `BookerNovelTool.openai`；新增依赖 numpy、jieba

v2026.10.26

+   从 BookerGptTool 迁移 `write-novel`、`gts-fiction`、`novel-anls` 三个子命令，独立建仓
+   精简通用 argparse 参数保持完整，仅注册三个子命令
