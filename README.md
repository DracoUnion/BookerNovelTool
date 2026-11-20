# BookerNovelTool

BookerNovelTool 是一个基于 OpenAI 兼容 API 的小说命令行工具集，提供小说生成、EPUB 小说拆书分析等功能。

## 安装

推荐使用 Python 3.8 或更高版本（项目声明支持 Python 3.6+）：

```bash
pip install git+https://github.com/DracoUnion/BookerNovelTool.git
```

也可以在源码目录中安装：

```bash
pip install .
```

安装后提供两个等价的命令：`novel-tool` 和 `BookerNovelTool`。

## 配置 API

工具通过 OpenAI 兼容接口访问大模型。至少需要设置 API Key：

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_CHAT_MODEL="gpt-4o-mini"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_CHAT_MODEL = "gpt-4o-mini"
```

`OPENAI_BASE_URL` 可替换为其他 OpenAI 兼容服务的地址。

不要把 API Key 提交到 Git 仓库或写入公开脚本中。

## 基本用法

查看帮助和版本：

```bash
novel-tool -h
novel-tool --version
novel-tool <子命令> -h
```

通用参数应放在子命令之前，例如：

```bash
novel-tool --model gpt-4o-mini --retry 3 write-novel "一名少年穿越到修仙世界"
```

常用全局参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-m, --model` | 聊天模型名称 | `OPENAI_CHAT_MODEL`，未设置时为 `gpt-3.5-turbo` |
| `-k, --key` | OpenAI API Key | `OPENAI_API_KEY` |
| `-H, --host` | API 地址 | `OPENAI_BASE_URL` |
| `-r, --retry` | 重试次数 | `1000000` |
| `-tm, --temp` | temperature | `1` |
| `-mt, --max-tokens` | 最大输出 token 数 | 不限制 |
| `-ST, --no-stream` | 关闭流式输出 | 关闭 |

## 子命令

### 小说生成（write-novel）

从一句简介生成中文网文，内置前置规划、开头计划、分卷章纲、黄金三章、逐章正文与一致性复查的完整工作流：

```bash
novel-tool write-novel "都市修仙：一名程序员的逆袭" -o novel -c 20
```

可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-o, --out` | 输出目录名 | `novel` |
| `-c, --chapters` | 计划写作章数 | `20` |
| `-ck, --check` | 一致性复查/返修轮数上限 | `3` |
| `-pv, --preview-len` | 上一章结尾供承接的截取字数 | `2000` |
| `-D, --debug`（全局） | 调试模式 | 关闭 |

### 小说生成（gts-fiction）

根据创意/题材生成小说，按"世界观 → 角色 → 大纲 → 细纲 → 正文 → 润色"的流程输出到指定目录：

```bash
novel-tool gts-fiction "一个关于时间旅行的悬疑故事" -o out
```

可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-o, --out-dir` | 输出目录 | 随机目录 |
| `-c, --chapters` | 章节数 | `20` |
| `-w, --words` | 字数 | `5000` |
| `-wc, --write_command` | 写作指令 | 内置 |
| `-pc, --polish_command` | 润色指令 | 内置 |
| `-se, --style-example` | 风格示例 | 空 |

### EPUB 小说拆书（novel-anls）

解析 EPUB 小说，并行扫描各章节，再并行聚合出题材定位、人物图谱、主线结构、节奏爽点、伏笔铺垫、可迁移模式等模块，输出 JSON 报告：

```bash
novel-tool novel-anls book.epub --book-title "书名" --author "作者"
```

可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-t, --threads` | 线程数 | `8` |
| `-mc, --max-chapters` | 处理章节数上限 | 无 |
| `--book-title` | 书名 | 无 |
| `--author` | 作者名 | 无 |
| `--blurb` | 书籍简介 | 无 |

### 小说风格/质量评价（metrics）

按 A/B/C/D 四档计算小说的风格与质量指标，输出 JSON 报告：

- **A 档（纯规则）**：字/词/句/段/章长度与分布、标点、词汇丰富度（TTR 家族）、熵/压缩率、句型、把被字句、语音（声调/押韵/生僻字，需 pypinyin）。
- **B 档（传统 NLP）**：词性/依存/NER（需 hanlp，可选）、情感/感官/风格词、主题网络（LDA/共现，需 gensim/networkx，可选）、可读性、风格相似度、衔接连贯。
- **C 档（必须 LLM）**：修辞识别、描写类型、叙事学特征、风格判断、全书结构。
- **D 档（规则 + LLM 级联）**：情感、主题、修辞、指代、视角、场景、对话/叙述比、描写类型、认知负荷、风格相似度；规则低置信度时才调用 LLM。

输入支持单个文本文件、EPUB（复用 novel-anls 的解析）或章节文本目录：

```bash
novel-tool metrics book.txt -o metrics_report.json
novel-tool metrics book.epub --tier ab --no-pos
novel-tool metrics chapters/ --budget 500
```

可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-o, --output` | 报告输出路径 | `metrics_report.json` |
| `-a, --asset-dir` | LLM 结果缓存目录 | `.metrics_cache` |
| `--tier` | 计算档位（`ab`/`c`/`d`/`all`） | `all` |
| `--budget` | LLM 调用预算上限 | `5000` |
| `--max-chars` | 单次 LLM 调用截取的文本长度 | `4000` |
| `--baseline` | 用于风格相似度对比的基准文本 | 无 |
| `--no-pos` / `--no-lexicon` / `--no-topic` / `--no-cohesion` / `--no-phonetic` | 跳过对应档位/模块 | 全部启用 |

说明：新增依赖 `numpy`、`jieba`；`hanlp`、`gensim`、`networkx`、`pypinyin`、`sentence-transformers` 为可选增强，缺失时相关指标自动降级并在报告中标记。

### 小说转文字游戏（comic）

把一本小说转化为可玩的状态化文字游戏：先离线解构出世界书（角色、地点、物品、规则）与初始状态，再进入对话式运行时，玩家输入行动，LLM 以角色口吻叙事，Python 侧严格维护世界状态（位置、背包、关系、标志）：

```bash
novel-tool comic book.txt -o game
```

建议加上 `-ST -TN` 关闭流式输出与思考模式，避免 LLM 返回空 content 导致 JSON 解析失败。

可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `novel` | 小说文本文件路径（UTF-8） | 必填 |
| `-o, --output` | 输出目录 | `<小说所在目录>/<书名>_game` |
| `--extract-only` | 仅执行离线资产抽取，不进入游戏运行时 | 关闭 |

输出：`worldbook.json`（世界书）、`initial_state.json`（初始状态）、`final_state.json`（最终运行时状态）。

### 小说解构与文字游戏运行时（gal-parse / gal-play）

把一部小说（EPUB/纯文本）离线解构为结构化游戏资产包，再通过状态化运行时引擎，用 OpenAI API 驱动可交互的中文文字游戏。LLM 只负责生成叙事与抽取结构化信息，世界真实状态由 Python 侧状态机维护：

```bash
# 第一步：解构小说为资产包（worldbook.json / scenes.json / initial_state.json / manifest.json）
novel-tool gal-parse book.epub -o game_assets

# 第二步：进入交互式文字游戏运行时
novel-tool gal-play game_assets -s save.json
```

建议加上 `-ST -TN` 关闭流式输出与思考模式，避免结构化 JSON 解析失败。

`gal-parse` 可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `input` | 小说文件路径（EPUB 或 UTF-8 纯文本） | 必填 |
| `-o, --out` | 资产包输出目录 | 必填 |
| `-c, --chapters` | 章节范围，如 `1-5` | 全部 |
| `--max-chars` | 单章截断长度 | `12000` |
| `--skip-existing` | source_hash 命中时跳过重复解析 | 关闭 |
| `--concurrency` | 章节并发解析数 | `4` |
| `--no-merge` | 跳过跨章实体合并（调试用） | 关闭 |
| `--validate` | 保存前对资产包做约 13 项确定性验收，失败退出非零码 | 关闭 |
| `--approve-worldbook` | worldbook 生成后暂停，等待人工确认再保存完整资产包 | 关闭 |

`gal-play` 可选参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `assets_dir` | `gal-parse` 产出的资产包目录 | 必填 |
| `-s, --save` | 存档路径，不存在则新建，存在则读档继续 | `<assets_dir>/save.json` |
| `--ui` | 界面模式 `plain`/`rich` | `plain` |
| `--max-turns` | 自动跑 N 轮后退出（测试用） | 不限 |
| `--script` | 脚本模式，逐行读取玩家输入（测试/回放） | 关闭 |
| `--log` | 每轮 TurnResult 追加写入 JSONL | 关闭 |

进入 REPL 后支持元命令：`/save`、`/load`、`/state`、`/quit`、`/help`。

## 常见问题

### 请求失败或认证错误

检查 `OPENAI_API_KEY` 是否有效，且 `OPENAI_BASE_URL` 是否包含正确的 API 路径。也可以通过命令行参数临时覆盖：

```bash
novel-tool -k "$OPENAI_API_KEY" -H "https://example.com/v1" write-novel "简介"
```

### 不知道某个命令有哪些参数

每个子命令都提供独立帮助：

```bash
novel-tool write-novel -h
novel-tool gts-fiction -h
novel-tool novel-anls -h
novel-tool metrics -h
novel-tool comic -h
```

## 开发

```bash
git clone https://github.com/DracoUnion/BookerNovelTool.git
cd BookerNovelTool
pip install -e .
```

项目主页：<https://github.com/DracoUnion/BookerNovelTool>
