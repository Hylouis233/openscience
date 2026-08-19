![openscience poster](docs/assets/poster.png)

# openscience

**Open scientific research workbench — literature → hypothesis → experiment → analysis → writing, with verifiable evidence, auditable provenance, and human gates, delivered as Claude Code / Kimi Code plugins.**

[Quick start](#quick-start) · [How it works](#how-it-works) · [Plugins](#plugins) · [中文快速上手](#中文快速上手) · [Design provenance](THIRD_PARTY_NOTICES.md) · [Architecture](docs/architecture.md)

openscience is a local-first plugin marketplace for doing real research with an AI
agent — without letting that agent grade its own homework. Literature search, reading,
survey, and writing are wired into one evidence loop: every claim in a draft must trace
to a retrieved `EvidenceItem`, every reference must survive automated verification, and
every stage stops at a human gate before moving on.

> [!IMPORTANT]
> This repository is a research workflow tool. It does not produce scientific conclusions,
> medical advice, or legal advice. All outputs are working drafts and must be reviewed by
> the researcher before use or publication. Verification never proves a claim true — it
> proves its citations and evidence trail are real and current.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and Claude Code or Kimi Code.

```bash
# Add the marketplace and install the core plugins
/plugin marketplace add Hylouis233/openscience
/plugin install science-core@openscience
/plugin install science-literature@openscience
/plugin install science-verify@openscience
```

Then, inside the agent:

```text
1. cold-start-interview   # one-time interview → your research profile (playbook)
2. research-workspace     # standard project layout (data/ figures/ papers/ output/ …)
3. literature-search      # multi-source retrieval (OpenAlex / Crossref / arXiv / CNKI / Wanfang)
4. literature-survey      # 8-field evidence mapping, EvidenceItem matrix
5. review-writing         # draft with whitelisted citations, GB/T 7714 output
6. citation-verify        # bibverify MCP checks every BibTeX entry against real sources
```

Optional plugins: `science-compute` (SSH/HPC/long runs), `science-data` (domain
database connectors), `science-epi` (epidemiology & public health).

## How it works

```text
 research question
   │
   ▼
 literature-search ──► papers.json (unified PaperDocument, fail-structured)
   │
   ▼
 paper-read ──► EvidenceItem {paper_id, claim, quote, page, confidence}
   │              (full-text or honestly marked abstract-only)
   ▼
 literature-survey ──► 8-field synthesis, evidence whitelists only
   │
   ▼
 review-writing ──► draft + references.bib (GB/T 7714)
   │
   ▼
 citation-verify (bibverify MCP) ──► verified / identifier_conflict / no_match
   │                                   (conflict ≠ not-found ≠ fabrication)
   ▼
 claim-check ──► unsupported claims ──► evidence-loop ──► targeted re-retrieval
   │
   ▼
 reviewer agent (read-only) + stage-gate: approve / revise / reject
```

Three contracts hold the loop together:

- **```review fence** — every checking skill emits the same fenced-JSON verdicts
  (`level / check / title / evidence / note`), consumed by one read-only reviewer agent.
- **Stage gates** — each stage writes its artifacts to disk *before* asking for
  `approve / revise / reject`; `revise` archives instead of overwriting, so the trail is
  append-only.
- **Provenance** — `record_run.py` appends every material action to
  `.openscience/provenance.jsonl` with an environment fingerprint (deduplicated by hash).

## Plugins

| Plugin | What it carries | Status |
| --- | --- | --- |
| science-core | Research profile (playbook), lifecycle router, stage-gate, provenance, evidence capsule, reviewer | ✅ |
| science-literature | literature-search / paper-read / literature-survey / review-writing / cn-literature (CNKI export parser + Wanfang API) | ✅ |
| science-verify | citation-verify (bibverify MCP), claim-check, evidence-loop | ✅ |
| science-compute | python/r-analysis, remote-compute (probe-then-contract), hpc-slurm, run-monitor (long-task Run abstraction) | ✅ |
| science-data | Connector registry with fail-closed license gate, domain retrieval playbooks | ✅ |
| science-epi | Outbreak analysis (linelist → epi curve / attack rates), SEIR modeling, spatial epi, epi writing | ✅ |

All connectors are optional and degrade honestly: a missing token or an unreachable
source produces a structured "source gap" note, never a silent omission.

## Repository map

```text
plugins/
  science-core/         workbench skeleton (CLAUDE.md profile + guardrails, 8 skills, 2 agents)
  science-literature/   retrieval → reading → survey → writing (+ search/extract scripts)
  science-verify/       evidence engine (bibverify MCP + 3 skills)
  science-compute/      kernels, SSH/HPC, long-task runs (+ 2 stdlib scripts)
  science-data/         connector fleet registry (connectors.yaml, fail-closed gate)
  science-epi/          epidemiology domain pack (+ epi_curve.py, seir.py)
evals/                  trigger-cases.json + automated runner (offline & LLM modes)
examples/               demo-workspace + demo-epi (fully worked, synthetic data)
docs/                   architecture.md, publishing.md, assets/
scripts/validate-skills.py   contract checker (stdlib, mirrors CI)
.github/workflows/      validate + weekly trigger evals (optional LLM secrets)
```

## 中文快速上手

安装后按顺序使用即可：先跑 `cold-start-interview` 生成研究画像，再用
`literature-search` 检索中英文文献（说一句"帮我查一下 XX 方向近三年的进展"即可触发），
综述与写作走 `literature-survey` → `review-writing`，投稿前必须过
`citation-verify` 核验参考文献——查不到不等于伪造，标识符冲突会单独列出。
每个阶段结束会停下来等你 `approve / revise / reject`，`revise "意见"` 会带着意见重跑当前阶段且不覆盖旧稿。
流行病学方向直接装 `science-epi`：暴发调查、SEIR、空间分析、公卫写作开箱即用。

## Design provenance

Clean-room implementation informed by published designs — see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the full registry
(ai4s-research/open-science, lamm-mit/scienceclaw, xuzhougeng/wisp-science,
anthropics/life-sciences, YUANXICHE98/LabOS, Tswoen/Paper-Agent, and
[Hylouis233/bibverify](https://github.com/Hylouis233/bibverify) as the verification MCP).
AGPL and unlicensed sources informed ideas only; every line here is original.

## Contributing

Start with [docs/publishing.md](docs/publishing.md). PRs must keep
`python scripts/validate-skills.py` green, ship original text only (no AGPL code
lifting), and preserve the fail-structured / honest-degradation semantics. Trigger evals
live in `evals/` — add cases with any new skill.

## License

[MIT](LICENSE) — Copyright (c) 2026 Hylouis233 and contributors.
