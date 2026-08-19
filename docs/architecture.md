# openscience 架构文档

本文档描述 openscience 插件集的设计原则、目录结构与关键机制。目标读者：插件开发者与贡献者。

## 设计原则

1. **SKILL.md 为唯一知识载体**。每个能力的全部知识都写在该 skill 的 `SKILL.md` 里，不依赖外部 wiki 或隐式约定。frontmatter 只保留极简的 `name` + `description`；`description` 同时承担触发器职责——模型靠它判断何时加载该 skill，因此必须写清「做什么、何时用」。
2. **统一 review 输出契约**。所有检查类 skill（核验、评审、lint）的输出使用 ` ```review ` 围栏 JSON，字段为：
   ```review
   {"level": "error|warn|ok", "check": "<检查名>", "title": "<一句话结论>", "evidence": "<依据>", "note": "<可选补充>"}
   ```
   reviewer agent 统一消费这些输出并汇总为总评，禁止各 skill 自创报告格式。
3. **阶段产物先落盘、再审批**。每个阶段的产物（检索结果、综述稿、核验报告）必须先写入磁盘，再进入审批流程；内存中的中间态不构成审批对象。
4. **human gate 两层**。第一层：危险操作（删除、远程提交、外部发布）走工具权限审批；第二层：成果发布前必须过 reviewer 门禁（stage-gate）。两层相互独立，不可互相替代。
5. **模型/数据源调用全部可降级、失败结构化**。任何外部调用（检索源、MCP server、模型）都必须有降级路径；失败以结构化对象返回（如 `{"status": "unavailable", "source": "...", "reason": "..."}`），**查不到 ≠ 不存在**，禁止把调用失败解释为阴性结果。
6. **证据核验是一等公民**。核验不是写作后的可选润色，而是流水线必经环节：未经核验的引用不得进入终稿。

## 目录结构

```
openscience/
├── .claude-plugin/
│   └── marketplace.json            # marketplace 清单（6 个插件）
├── plugins/
│   ├── science-core/               # 科研工作台骨架
│   │   ├── .claude-plugin/plugin.json
│   │   ├── CLAUDE.md               # 研究画像模板 + Shared guardrails（canonical）
│   │   ├── skills/                 # cold-start-interview / research-lifecycle /
│   │   │                           # research-workspace / stage-gate / provenance-record /
│   │   │                           # evidence-capsule / reviewer-protocol / customize
│   │   ├── agents/                 # reviewer（只读审稿）/ literature-watcher（定时追踪）
│   │   └── hooks/hooks.json        # 空壳（护栏在 prompt 层）
│   ├── science-literature/         # 文献链路
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/                 # literature-search（路由器）/ paper-search（库 skill，
│   │       │                       # 含 scripts/search_papers.py：OpenAlex/Crossref/arXiv）
│   │       │                       # literature-survey / paper-read / review-writing /
│   │       │                       # cn-literature（CNKI 题录解析 + 万方 API）
│   ├── science-verify/             # 证据核验
│   │   ├── .claude-plugin/plugin.json
│   │   ├── .mcp.json               # bibverify MCP server（uvx bibverify mcp）
│   │   └── skills/                 # citation-verify / claim-check / evidence-loop
│   ├── science-compute/            # 科研计算
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/                 # python-analysis（含 stats_integrity_check.py）/
│   │                               # r-analysis / remote-compute / hpc-slurm /
│   │                               # run-monitor（含 run_task.py 长任务管理）
│   ├── science-data/               # 数据库 connector
│   │   ├── .claude-plugin/plugin.json
│   │   ├── .mcp.json               # 按域聚合的 MCP 指针
│   │   ├── references/connectors.yaml  # 元数据表 + deferred 清单（fail-closed）
│   │   └── skills/                 # scientific-databases（按域检索规程）
│   └── science-epi/                # 流行病学域包
│       ├── .claude-plugin/plugin.json
│       └── skills/                 # epi-data-access / outbreak-analysis（含 epi_curve.py）/
│                                   # seir-modeling（含 seir.py）/ spatial-epi / epi-writing
├── evals/
│   ├── trigger-cases.json          # skill 触发评测集
│   └── run_trigger_evals.py        # 触发评测运行器
├── examples/demo-workspace/        # 标准研究工作区骨架示例
├── scripts/
│   └── validate-skills.py          # 结构与契约校验（stdlib，无第三方依赖）
├── .github/workflows/validate.yml  # CI：契约校验 + 脚本语法检查
├── docs/
│   ├── architecture.md             # 本文档
│   └── publishing.md               # marketplace 发布指南
├── LICENSE                         # MIT
├── README.md
└── THIRD_PARTY_NOTICES.md
```

## 关键机制

### slug 契约

每个研究主题（topic）经规范化（Unicode NFKC 规范化、转小写、去首尾空白、连续空白折叠为单个空格）后取 `sha1(规范化后 topic 的 UTF-8 字节)[:8]` 得到稳定 slug。该 skill 的所有产物写入 `output/<skill-name>/<slug>/latest/` 目录。同一 slug 重复运行时，`latest/` 指向最新版本，旧版本归档（见 stage-gate 的 revise 语义），保证「同主题产物可定位、可复现、不互相覆盖」。

### stage-gate 三态

阶段审批结果为 `approve / revise / reject` 三态，写入产物目录旁的 `stage.yaml`（含阶段名、结论、时间、审批人/会话、意见）：

- **approve**：产物冻结，允许进入下一阶段。
- **revise**：当前 `latest/` 归档为带时间戳的历史版本，新修订写入新的 `latest/`——归档不覆盖。
- **reject**：产物不进入下一阶段，`stage.yaml` 记录驳回理由，回到上一环节重做。

### provenance.jsonl

工作区根目录的 `.openscience/provenance.jsonl` 全局唯一一份，append-only，记录每次外部数据获取与关键动作：时间戳、产物路径（paths）、来源（工具/模型/会话）、note；环境详情（python 版本、平台等）按 env_hash 内容寻址去重，存于 `.openscience/env/<hash>.txt`。审计时可从任意结论回溯到原始来源，且日志只增不改。

### Evidence Capsule 四级能力

证据胶囊对每条证据诚实标注可验证能力等级，禁止夸大：

- **archived**：原始响应已存档（可出示快照）。
- **traceable**：存档之上，来源与获取过程可回溯（有 provenance 记录链）。
- **re_executable**：获取/计算脚本可重新执行（有环境与入口）。
- **reproduced**：已实际重跑并与原结果比对一致。**未重跑比对不得声称 reproduced**。

### 证据闭环

```
literature-search → literature-survey 产 EvidenceItem 矩阵
  → review-writing 仅从证据白名单生成引用（GB/T 7714）
  → citation-verify 核验参考文献真实性（bibverify MCP）
  → claim-check 逐条检查 claim 支撑，标记 unsupported
  → evidence-loop 对 unsupported 定向补检
  → 修订稿件 → 复验，直至全部 claim 有支撑或显式删除
```

## 数据合规

- **CNKI**：不抓取、不绕过验证码；用户官网检索后导出题录，经 `cn-literature` 的解析脚本转为 PaperDocument。万方走官方开放平台 API（`WANFANG_TOKEN`，未配置降级）。
- **商业数据源**：API key 一律通过环境变量注入，skill 文档只引用变量名。
- **仓库零凭证**：本仓库及产物目录中禁止提交任何密钥、token 或个人凭证；校验脚本与 review 流程应把疑似凭证作为 error 级问题报告。

## 版本与迭代

**当前版本（0.2.0）**：6 个插件全部可用。文献链已闭环：literature-search → paper-read（全文提取/abstract-only 诚实降级）→ literature-survey（8 字段证据映射）→ review-writing → citation-verify/evidence-loop。

**迭代记录（0.2.x）**：science-compute（SSH/Slurm/run_task 长任务）、science-data（connector 元数据表 + fail-closed 清单）、science-epi（流行病学域包）、cn-literature（中文文献）、paper-read（pdf_extract 三级降级链）；评测自动化 `evals/run_trigger_evals.py`（离线结构校验 + `--llm` 命中率模式）。

**后续方向**：万方 token 实测与更多中文源接入、run_task 与 HPC 的联动（Slurm 作业纳入 Run 抽象）、LLM 评测定时化、示例工作区扩展到 epi 完整案例。
