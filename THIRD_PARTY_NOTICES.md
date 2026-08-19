# 第三方声明（Third-Party Notices）

本项目在设计上借鉴了以下开源项目的思路与契约设计。我们感谢这些项目的作者与社区。

| 项目 | URL | License | 借鉴内容 |
| --- | --- | --- | --- |
| ai4s-research/open-science | https://github.com/ai4s-research/open-science | MIT | skills 组织方式与 review 输出契约 |
| lamm-mit/scienceclaw | https://github.com/lamm-mit/scienceclaw | Apache-2.0 | artifact 与技能契约设计 |
| xuzhougeng/wisp-science | https://github.com/xuzhougeng/wisp-science | AGPL-3.0 | **仅设计思想**：connector 分层与证据四级能力 |
| anthropics/life-sciences | https://github.com/anthropics/life-sciences | Apache-2.0 | marketplace 格式 |
| YUANXICHE98/LabOS | https://github.com/YUANXICHE98/LabOS | AGPL-3.0 | **仅设计思想**：阶段审批三态 |
| Tswoen/Paper-Agent | https://github.com/Tswoen/Paper-Agent | 无 license | **仅设计思想**：证据映射白名单 |
| Hylouis233/bibverify | https://github.com/Hylouis233/bibverify | MIT | 作为 MCP server 接入（见 `plugins/science-verify/.mcp.json`） |

## 运行时数据源与 connector（不随仓库分发代码）

| 资源 | 性质 | 使用方式 |
| --- | --- | --- |
| OpenAlex / Crossref / arXiv | 开放学术数据（CC0/开放 API） | `paper-search` 脚本直连公开 API，遵守各源 politeness 要求 |
| 万方数据开放平台 | 商业授权（api.wanfangdata.com.cn） | `cn-literature` 脚本，用户自备 `WANFANG_TOKEN`；未配置时降级 |
| CNKI 中国知网 | 商业数据库 | 不抓取；用户官网检索后导出题录，仓库仅提供题录解析脚本 |
| PubMed / Europe PMC / Semantic Scholar | 开放 API | 经 paper-search MCP connector 或脚本访问 |
| science-data 策划的 connector（paper-search-mcp、biomcp、materials-project、fred、spaceweather、open-meteo、usgs-water 等，部分为 HTTP 直连，详见 `plugins/science-data/references/connectors.yaml` 登记） | 各自开源 license（见 connectors.yaml 登记） | 以 `uvx`/HTTP 在运行时装配，代码不进入本仓库；license 风险源集中在 deferred 清单列出禁用项（fail-closed） |
| WHO / GHDx(IHME) / Our World in Data / ProMED / 国家卫健委通报 / China CDC Weekly | 各自数据使用条款 | `science-epi` 数据源指引；个案数据遵循去标识化红线 |

## 原创性声明

本仓库的**所有文本与代码均为原创撰写**，未从上述任何上游仓库复制代码、文档或其他内容。对标注「仅设计思想」的项目（尤其是 AGPL-3.0 与无 license 的项目），我们仅参考其公开的设计概念并独立实现，不包含、不衍生其源代码。bibverify 为本项目作者本人的独立项目，以 MCP server 形式在运行时装配调用，其代码不包含在本仓库中。

各上游项目的 license 原文请见其各自仓库。如任何权利人认为本声明有遗漏，欢迎提 issue 指正。
