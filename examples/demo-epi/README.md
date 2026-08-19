# demo-epi：流行病学完整链路示例工作区

**本目录全部内容为虚构的教学演示数据，不对应任何真实疫情、真实地点与真实人群。**

`demo-epi/` 演示 science-epi 插件集五个 skill 的端到端链路：数据源获取 → 暴发分析 → 模型推演 → 报告成稿 → 引用核验。

## 目录结构

```text
demo-epi/
├── data/
│   └── linelist.csv                                  # 虚构病例一览表（30 例，甲/乙/丙三村）
├── output/
│   ├── outbreak-analysis/e5c07d31/latest/curve.json  # epi_curve.py 真实运行输出
│   └── seir-modeling/e5c07d31/latest/seir.json       # seir.py 真实运行输出（series 截断，见文件内 note）
└── reports/
    └── outbreak-report-v1.md                         # 暴发调查报告骨架（数字均可回溯到上述产物）
```

`e5c07d31` 是演示用项目 slug；产物路径契约与 demo-workspace 一致：`output/<skill 名>/<slug>/latest/`。

## 五步链路走查

### 1 · epi-data-access：数据从哪来

真实场景：按 epi-data-access 规程确定数据源（入口、格式、许可注意、来源标注标签四要素），个案数据先过去标识化红线检查，进 `data/` 即冻结。
本示例：`data/linelist.csv` 为手工虚构（30 例；发病日期 2026-07-06 至 2026-07-19 跨 14 天；`case_type` 分疑似/临床/确诊三档；`village` 分甲村/乙村/丙村），视同已去标识化的冻结原始数据，不改名、不编辑、不覆盖。

### 2 · outbreak-analysis：流行曲线与罹患率

```bash
cd examples/demo-epi
python ../../plugins/science-epi/skills/outbreak-analysis/scripts/epi_curve.py \
  data/linelist.csv --group-by village --population 甲村=430,乙村=560,丙村=810 \
  --format json > output/outbreak-analysis/e5c07d31/latest/curve.json
```

关键结果：共 30 例（确诊 13 / 临床 10 / 疑似 7）；单日高峰 2026-07-11（5 例）；甲村罹患率 3.49%，高于乙村 1.79%、丙村 0.62%（分村人口为虚构设定值）。

### 3 · seir-modeling：传播情景推演

```bash
python ../../plugins/science-epi/skills/seir-modeling/scripts/seir.py \
  --model seir --beta 0.6 --sigma 0.2 --gamma 0.1 \
  --population 50000 --i0 5 --days 120 --format json
```

仓库内的 `seir.json` 把逐日 121 点截断为每 5 天一点（文件内 `note` 字段有说明），`peak`、`r0` 与其余字段为脚本原样输出。
关键结果：R0 = 6.0；该情景下第 53 天感染人数达峰（约 16867 人）。模型输出是条件推演而非预测，参数假设随产物一并记录。

### 4 · epi-writing：报告成稿

按 epi-writing 的暴发调查报告结构（背景/方法/结果/控制措施/讨论五节）成稿，每个数字挂产物来源标签。成稿见 `reports/outbreak-report-v1.md`。

### 5 · citation-verify：交稿前引用核验

报告引用外部文献或数据源时，按 citation-verify 规程逐条核验存在性与论断-证据映射。本示例数字全部来自本地虚构产物、无外部引用，此步形式上从简；真实场景不可省。

## 如何照这个示例走一遍

1. 安装插件（见 [../../docs/publishing.md](../../docs/publishing.md)）：至少 `science-core`、`science-epi`、`science-verify`。
2. 初始化工作区（research-workspace），把去标识化 linelist 放入 `data/` 冻结。
3. 依次对 Claude 说："分析这份病例一览表"（outbreak-analysis）→"跑一个 SEIR 看看峰值"（seir-modeling）→"把这次暴发调查写成报告"（epi-writing）→"核验报告引用"（citation-verify），产物路径即与本示例同构。
