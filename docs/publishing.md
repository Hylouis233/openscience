# 发布指南：openscience marketplace

本文面向维护者与贡献者，说明本仓库作为 Claude Code / Kimi Code 插件 marketplace 的发布、版本管理与贡献流程。使用者安装说明见 [README.md](../README.md) 与下文第 1 节。

## 1. 用户如何安装

仓库推送到 GitHub 后，用户有两种方式添加 marketplace：

```text
# 方式一：GitHub owner/repo 简写
/plugin marketplace add <owner>/openscience

# 方式二：完整 git URL（等价，适用于自托管 Git 服务）
/plugin marketplace add https://github.com/<owner>/openscience.git
```

添加后按需安装插件：

```text
/plugin install science-core@openscience
/plugin install science-literature@openscience
/plugin install science-verify@openscience
```

要点：

- `science-core` 是骨架插件，其余插件依赖它定义的契约（provenance、证据胶囊、review 围栏、产物路径），应建议用户**先装 science-core**。
- marketplace 名 `openscience` 来自 `.claude-plugin/marketplace.json` 的 `name` 字段，改名会破坏既有用户的 `@openscience` 引用，视为破坏性变更。
- Kimi Code 支持同一套目录规范（`.claude-plugin/plugin.json`、`skills/*/SKILL.md`、`.mcp.json`），同一仓库无需额外适配。

## 2. 版本管理

仓库里有两层版本号，各司其职：

| 版本号 | 位置 | 含义 | 何时提升 |
| --- | --- | --- | --- |
| 插件版本 | `plugins/<name>/.claude-plugin/plugin.json` 的 `version` | 单个插件自身的版本 | 该插件内容有任何变更时 |
| marketplace 版本 | `.claude-plugin/marketplace.json` 的 `metadata.version` | 整个 marketplace 的发布版本 | 每次对外发布（含任何插件变更） |

同步规则：

1. **只改哪个插件，就升哪个插件的 `plugin.json` version**；未变更的插件版本号不动。
2. **每次发布必升 `metadata.version`**，提升幅度（major/minor/patch）取本次所有插件变更中最高的一档。
3. 对外打 tag 时使用 `v<metadata.version>`（如 `v0.2.0`），保证 tag、marketplace 版本一一对应，用户可按 tag 锁定版本。
4. 两层版本号独立演进，不要求相等；但同一时刻 `metadata.version` 应能回答"当前 marketplace 整体处于哪个发布"。

语义化版本（semver）口径：

- **MAJOR**：破坏契约的变更——frontmatter 字段变更、`output/<skill>/<slug>/latest/` 产物路径契约变更、```review 围栏输出契约变更、插件或 skill 改名/删除。
- **MINOR**：向后兼容的新增——新插件、新 skill、新数据源 connector、已有 skill 的能力扩展。
- **PATCH**：不改变行为的修正——文案、描述、注释、示例修订。

## 3. 发布检查清单

每次发布前逐项确认：

- [ ] `python scripts/validate-skills.py` 本地全绿（skill frontmatter 契约 + JSON manifest + marketplace 源目录完整性）。
- [ ] GitHub Actions `validate` workflow（`.github/workflows/validate.yml`）在 main 分支为绿：除上述校验外，还对仓库内所有 Python 脚本做语法检查。
- [ ] 变更插件的 `plugin.json` version 已按上节口径提升；`marketplace.json` 的 `metadata.version` 已提升。
- [ ] 插件清单同步：`marketplace.json` 的 `plugins` 列表与 [README.md](../README.md) 的「插件清单」表一致（名称、说明、状态），新增插件两边都已登记。
- [ ] 新增第三方参考、代码片段或数据已在 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) 登记，且许可证与 MIT 兼容。
- [ ] 新增/变更 skill 的 `metadata.last_reviewed` 已刷新为发布当天（`YYYY-MM-DD`）。
- [ ] 相关 `docs/` 文档已同步更新。

## 4. 本地开发循环

开发 skill 时不需要走 GitHub 发布流程，两种本地方式：

```text
# 方式一：单插件直接加载（改完即测，最快）
claude --plugin-dir ./plugins/science-core

# 方式二：本地路径添加 marketplace（测试完整安装链路）
/plugin marketplace add /path/to/openscience
/plugin install science-literature@openscience
```

注意事项：

- 方式二安装的是添加时刻的副本，**修改仓库文件后需要重新 install（或重启会话）才会生效**；调试单个插件时优先用方式一。
- 提交前必跑 `python scripts/validate-skills.py`，与 CI 完全同源，本地不过则 CI 一定不过。
- Windows 路径按 README 示例写盘符绝对路径（`C:/...`）；macOS/Linux 用对应绝对路径即可。

## 5. 贡献指南要点

### 新 skill 的 frontmatter 规范

校验脚本（`scripts/validate-skills.py`）强制以下契约，CI 不通过即不可合并：

```yaml
---
name: my-new-skill            # 必填，kebab-case，必须与 skill 目录名完全一致
description: >-               # 必填，至少 50 字符；写清"什么时候该用我"
  当用户……时使用。……（触发场景是 skill 被路由命中的唯一依据，
  务必包含同义说法与典型用户话术。）
metadata:
  domains: [literature, verification]   # 建议：领域标签
  last_reviewed: '2026-08-19'           # 可选；若写必须 YYYY-MM-DD
---
```

此外，所有 JSON manifest（`marketplace.json`、`plugin.json`、`.mcp.json`、`hooks.json`）必须能解析，marketplace 中登记的每个插件源目录必须存在且含 `.claude-plugin/plugin.json`——这些同样由校验脚本覆盖。

### 原创性要求

- skill 文本（SKILL.md、references、模板）必须是**原创写作**。不接受从其他插件仓库、prompt 集合或书籍中整段搬运的 skill，无论是否标注来源。
- 借鉴了第三方项目的设计思路或少量素材时，在 `THIRD_PARTY_NOTICES.md` 登记来源与许可证。
- 示例数据一律虚构并显式标注（参见 `examples/` 下的演示工作区）。

### License 兼容红线

- 本仓库以 [MIT](../LICENSE) 发布。**不接收 AGPL（以及 GPL 等 copyleft 许可证）代码的搬运或改写**——这会污染整个仓库的分发条款。
- 可接受的第三方素材许可证：MIT、BSD、Apache-2.0、CC-BY 及同等宽松条款，且必须登记。
- 不接收来源不明的数据集、爬取内容或无法确认授权状态的文本。

### 行为契约

- 检查类 skill 的输出统一为 ```review 围栏 JSON（level / check / title / evidence / note），由 reviewer agent 消费；新增检查类 skill 必须遵守该契约。
- 运行产物一律写入 `output/<skill>/<slug>/<timestamp>/` 并同步 `latest/`，契约细节见 `research-workspace` skill。
- 外部数据获取与模型调用经 `provenance-record` 登记到 `.openscience/provenance.jsonl`，不绕过。
