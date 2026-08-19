# openscience 示例

本目录提供可照抄的示例，演示 openscience 插件集的约定在真实使用中的样子。**所有示例内容均为虚构的教学演示数据，不对应真实文献与真实研究。**

## demo-workspace/：标准科研工作区骨架

`demo-workspace/` 演示 `research-workspace` skill 定义的标准目录约定：

```text
demo-workspace/
├── data/            # 原始数据，只读。到手后不再修改
├── figures/         # 论文/报告用图的最终版本（由 output 精选而来）
├── notebooks/       # Jupyter / Quarto 等交互式笔记本
├── papers/          # 论文与报告文稿（草稿与版本）
├── reports/         # 阶段性报告、组会材料
├── reviews/         # 审稿意见、reviewer agent 审查记录
├── scripts/         # 可重复执行的脚本（分析、作图、数据处理）
├── output/          # 各 skill 的运行产物（产物路径契约见下）
└── .openscience/    # 工作台元数据：provenance.jsonl 等
```

产物路径契约：`output/<skill 名>/<slug>/<timestamp>/` 存放每次运行的完整产物，`output/<skill 名>/<slug>/latest/` 是最近一次运行的副本，下游 skill 一律从 `latest/` 读。示例中 `a1b2c3d4` 是演示用的项目 slug（由 research-lifecycle 生成）。

包含两份演示产物：

- `output/literature-search/a1b2c3d4/latest/papers.json` —— 多源检索去重后的 PaperDocument 数组（3 条虚构记录，格式与真实产物一致，字段契约见 `plugins/science-literature/skills/literature-search/`）。
- `output/literature-survey/a1b2c3d4/latest/survey.md` —— 按 8 个固定字段组织的综述分析底稿骨架，论断挂 `[paper_id]` 证据引用。

以及 `.openscience/provenance.jsonl` 的两行示例登记记录（append-only 溯源流水账）。

## demo-epi/：流行病学完整链路示例工作区

`demo-epi/` 演示 science-epi 五个 skill 的端到端链路：epi-data-access（数据源规程）→ outbreak-analysis（epi_curve.py 流行曲线与罹患率）→ seir-modeling（seir.py 情景推演）→ epi-writing（暴发调查报告骨架）→ citation-verify（交稿前引用核验）。linelist 与产物全部为虚构；`curve.json`、`seir.json` 是配套脚本对虚构数据的真实运行输出。走查说明见 [demo-epi/README.md](demo-epi/README.md)。

## 如何照这个骨架开始一个新研究项目

1. 安装插件（见 [docs/publishing.md](../docs/publishing.md) 第 1 节）：至少 `science-core`，文献链路加 `science-literature`、`science-verify`。
2. 在你的新项目空目录里启动 Claude Code，运行 `cold-start-interview` 完成研究画像（只做一次）。
3. 运行 `research-workspace init`（或对 Claude 说"初始化工作区"）：它会创建上述九个标准目录、初始化 `.openscience/provenance.jsonl`、生成 `WORKSPACE.md`——结果就与 `demo-workspace/` 同构。
4. 对 `research-lifecycle` 说出你的研究主题，它会生成项目 slug（如 `3f9a1c7e`）并建立 `output/research-lifecycle/<slug>/`。
5. 用 `literature-search` 检索：产物落在 `output/literature-search/<slug>/latest/papers.json`，格式同示例（示例中的记录为虚构，真实产物来自实际数据源）。
6. 用 `literature-survey` 做证据映射综述：产出 `evidence.json` 与 8 字段 `survey.md`，骨架同示例。
7. 之后按 README「快速开始」继续 `review-writing` 与 `citation-verify`。

日常纪律（demo-workspace 各目录 README 有一行版速查）：

- 原始数据进 `data/` 即冻结，不改名、不编辑、不删除；
- 过程产物只去 `output/`，给人看的精选版本才复制到 `figures/`、`papers/`；
- 关键产物经 `provenance-record` 登记，"记录才算存在"。
