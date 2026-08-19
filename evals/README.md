# Skill 触发评测集

本目录存放 openscience 插件仓库的 **skill 触发评测集**，用于回答一个问题：

> 用户说某句话时，正确的 skill 是否被触发（加载）？

评测思路参考 skill-creator 的 evals：每条用例是一句真实用户口语（utterance），标注期望触发的插件与 skill，逐条或批量跑后比对实际加载的 skill 是否一致。

## 文件

- `trigger-cases.json` — 评测用例。用例总数与正/负例分布以 `trigger-cases.json` 实际内容为准，可用 `python evals/run_trigger_evals.py` 查看。

## 数据格式

```json
{"version": 1, "cases": [{"id": "os-001", "utterance": "...", "expected_plugin": "science-core", "expected_skill": "cold-start-interview", "should_trigger": true}]}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `id` | 用例编号，`os-` 前缀 + 三位序号，新增用例顺延编号，不复用旧编号。 |
| `utterance` | 用户原话，中文口语，长短与措辞尽量多样。 |
| `expected_plugin` | 期望触发 skill 所属插件名；用例与任何插件都无关时为 `null`。 |
| `expected_skill` | 期望触发的 skill 名（即 `plugins/<plugin>/skills/` 下的目录名）；期望不触发任何 skill 时为 `null`。 |
| `should_trigger` | `true`：正例，期望 top-1 命中 `expected_skill`。`false`：负例（易误触发的相邻场景），期望**不触发 note 中所指的陷阱 skill**；`expected_skill` 非空时还应命中那个更合适的 skill，为 `null` 时本仓库任何 skill 都不应触发。 |
| `note` | 仅负例携带，说明陷阱在哪、哪个 skill 不应被触发（含库技能应由调用方加载的说明）。 |

## 评测方法

**手动评测（推荐，最贴近真实使用）：**

1. 在 Claude Code / Kimi Code 中安装本仓库插件。
2. 每条用例开一个**全新会话**（避免上下文污染），原样粘贴 `utterance`。
3. 观察实际加载（被选中触发）的 skill，与 `expected_skill` 比对并记录：
   - 正例：实际触发的 top-1 skill == `expected_skill` 记为命中。
   - 负例：`note` 所指陷阱 skill 未被直接触发；且 `expected_skill` 非空时实际命中它、为 `null` 时无任何 skill 触发，记为通过。
4. 将结果按用例 id 记录成表格，统计命中率。

**半自动 / harness 批量评测：**

- 用脚本逐条把 `utterance` 作为独立用户输入送入待测 CLI（每条独立会话），抓取实际加载的 skill 列表（可从会话日志、调试输出或 hook 中读取），与期望值自动比对。
- harness 由使用方自行实现，本仓库不附带；判定口径与手动评测一致。

## 通过标准

- 正例 top-1 命中率 **≥ 90%**。
- 负例：陷阱 skill 的误触发率应为 **0**（个别边界用例可放宽到整体负例通过率 ≥ 90%）；库技能（claim-check、paper-search、reviewer-protocol）绝不直接面向用户触发。
- 未达标时优先检查对应 SKILL.md 的 `description` 是否写清了"什么时候用、什么时候不用"，再补充用例。

## 如何补充新用例

1. 在 `cases` 末尾追加，id 顺延（如 `os-072`），保持 JSON 合法（改完跑 `python -c "import json;json.load(open('evals/trigger-cases.json',encoding='utf-8'))"` 验证）。
2. 正例：用真实口语，避免与已有用例逐字重复；同义表达（如"查文献 / 帮我找找论文 / 检索一下"）应分散到不同用例。
3. 负例：选相邻、易混淆的场景——同一插件内的兄弟 skill、跨插件的近义任务、库技能的调用方路由；必须写 `note` 指明陷阱 skill。
4. 新增或重命名 skill 时，同步补充/修改对应用例；每个用户可直接调用的 skill 保持至少 2 条正例，每个插件保持至少 2 条负例。

## 说明

- 本评测为**人工 / 半自动**性质，不随 CI 强制执行；评测结果取决于所测模型与运行时，仅作 skill 描述质量的回归参考。
- 若某个 `expected_skill` 对应的 `plugins/*/skills/` 目录尚不存在（正在建设中），跑评测时跳过相关用例并在结果中标注 missing，不要按失败计。

## 自动化运行

`run_trigger_evals.py`（纯 Python 标准库，无需安装依赖）提供两种自动化模式，判定口径与上文"评测方法 / 通过标准"一致。

### 离线结构校验（默认，无网络无凭证）

```bash
python evals/run_trigger_evals.py                  # 文本报告
python evals/run_trigger_evals.py --format json    # 机器可读报告
python evals/run_trigger_evals.py --cases os-01,os-05   # 只跑 id 前缀匹配的用例
```

校验评测集本身：JSON 语法、id 唯一、必备字段齐全、`should_trigger` 为 bool、正例 `expected_skill` 对应目录存在于 `plugins/<plugin>/skills/<skill>`、负例必须带 `note`；同时扫描全部 SKILL.md 的 `description` 长度分布并报告（< 50 字符告警）。全部通过 exit 0，任一结构错误 exit 1。

### LLM 路由评测（--llm，需 OpenAI 兼容端点）

把仓库内全部用户可调用 skill（排除 `user-invocable: false` 的库技能）的 name + description 作为候选清单，逐条用例询问模型应触发哪个 skill，再自动判定：

```bash
export EVAL_LLM_BASE_URL="https://api.openai.com/v1"   # OpenAI 兼容端点
export EVAL_LLM_API_KEY="sk-..."
export EVAL_LLM_MODEL="gpt-4o-mini"
python evals/run_trigger_evals.py --llm
python evals/run_trigger_evals.py --llm --threshold 0.9 --timeout 60 --format json
```

判定规则：正例 top-1 命中 `expected_skill` 记为命中；负例要求返回 `null` 或未触发 `note` 中的陷阱 skill。汇总 `hit_rate` / `false_trigger_rate` / `errors`，`hit_rate` 低于阈值（默认 0.90，`--threshold` 可调）或负例通过率低于阈值时 exit 1。未配置环境变量时打印配置指引并 exit 2（不会崩溃）。网络失败自动重试 1 次，仍失败则该用例记 error 并继续。

### CI 建议

- **离线结构模式**：无外部依赖、秒级完成，建议纳入 CI（每次 PR 触发），保证评测集与插件目录结构始终一致。
- **LLM 模式**：依赖外部模型且有调用成本，结果随模型波动，建议定时任务或手动触发，不阻塞 PR；未达标时按"通过标准"一节的指引优先修 SKILL.md 的 description。
