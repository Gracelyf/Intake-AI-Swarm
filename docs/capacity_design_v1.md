# Capstone Day 3 — capacity 表设计（v1，2026-10-27 晚，为 Day 2 今晚 19:00–21:00 剩下的时间 / Day 3 建表准备）

按 `cases_transitions_design_v1.md` 和 `capstone_day2_decisions_v1.md` 的顺序：
Day 2 是 cases / transitions 表，接下来就是 capacity 表（FTE 与每月 completions），
为 concept v1 验收问题 4（+20% 情景）服务。**只写设计，不建表、不碰 appeals.db。**

## 这张表要回答的问题（concept v1 验收问题 4，原话）

> If Section B intake rises 20%, what happens to backlog and staffing?

概念稿已定算法（deterministic queue arithmetic，labelled scenario, not forecast）：

- `Inventory(t+1) = Inventory(t) + Intake(t)×1.2 − Completions(t)`
- 等待时间用 Little's Law：`W = inventory ÷ monthly completions`
- FTE 缺口：`added cases × hours per case ÷ effective hours per FTE`
- 输出：3–6 个月 backlog 路径 + “to hold backlog flat, +X FTE or +Y% capacity”，附 sensitivity range。

## 建议的表结构（只加新表，不改 annual_real / monthly_modelled / cases_modelled / transitions_modelled）

```sql
CREATE TABLE capacity_modelled (
  fiscal_year TEXT,                  -- '2024-25'
  calendar_month TEXT,               -- '2024-07'，与 monthly_modelled.calendar_month 对齐
  series TEXT,                       -- 'objections' 起步；CPP/EI、relief 后加
  section TEXT,                      -- v1 只做 'B'（见下：为什么 A 先不做）
  completions_modelled INTEGER,      -- 当月 B 的办结数（synthetic，由年度 processed 拆分）
  fte_modelled REAL,                 -- v1 留 NULL：没有已核的 FTE 来源，不编人数
  hours_per_case REAL,               -- 脚本参数，见下
  effective_hours_per_fte_month REAL, -- 脚本参数，见下
  source_tier TEXT,                  -- 'synthetic_modelled'
  method TEXT,
  PRIMARY KEY (fiscal_year, series, section, calendar_month)
);
```

## 校准规则（Day 1 / Day 2 同款做法：年度总数必须严丝合缝）

- **每月 completions 由年度 processed 拆分，不另外编总量。**
  已核的 objections processed：2023–24 是 82,764，2024–25 是 118,077
  （`appeals_annual_anchor_v3.md`，CRA Departmental Results Report 已核）。
- **拆分形状：v1 用每月均分（flat），不用 intake 的报税季形状。**
  理由：办结是人力产出，比进件平滑；均分让 backlog 在进件高峰月（7 月）自然累积、
  在低峰月自然消化，+20% 情景才有可比的路径。形状是脚本参数，改参数重跑即可。
  算术已验：118,077 ÷ 12 = 9,839.75 → 9 个月 9,840 + 3 个月 9,839 = 118,077；
  82,764 ÷ 12 = 6,897 整除。
- **2022–23 不建 completions 行。** 该年 processed 在 annual_real 里是空值
  （无官方来源，v3 明确警告不要从 +7% 这类四舍五入的百分比反推填数）。
  2022–23 的 completions 保持缺失，不估算。
- **Section A 先不做。** A 的办结 = 离开 A 的案子（去 B + 在 A 内结案），
  年度 processed 只给总办结数，不分 Section，无法按 Section 校准。
  v1 只做 B（+20% 情景问的就是 B）；A 的 capacity 是 open item，见下。

## 脚本参数（全是假设，不是 CRA 数据；放脚本顶部，改了重跑）

| 参数 | v1 推荐值 | 说明 |
|---|---|---|
| `COMPLETIONS_SHAPE` | flat（每月均分） | 见上；备选：跟 intake 同形状（需 Liang 确认办结也有季节性才用） |
| `HOURS_PER_CASE_B` | 4 小时 | 纯假设：B 实质审理每案平均工时。**必须由 Liang 确认或改**，没有来源 |
| `EFFECTIVE_HOURS_PER_FTE_MONTH` | 140 小时 | 纯假设：35 小时/周 × 4 周。同样待确认 |
| `FTE_MODELLED` | NULL | 不编 FTE 人数；FTE 缺口由公式算出，不靠存量 FTE |

## 用已有数字验算一遍 +20% 情景（2024 年 7 月，峰值月）

已有数（都已在库里或已核过）：

- 2024 年 7 月 objections 进 A：15,406（monthly_modelled，峰值月）
- 进 B 的约数：15,406 × 0.04（2026-10-30 定的转移率）≈ 616
- +20% 后多出的 B 进件：≈ 123 案/月
- 多出工时：123 × 4 小时 ≈ 493 小时
- **hold-flat 所需 FTE：493 ÷ 140 ≈ 3.5 FTE（该月）**

这只是设计稿里的验算示例，不是结论：HOURS_PER_CASE_B 一改，3.5 这个数就跟着变。
情景工具输出时必须同时报 sensitivity range（例如 hours per case 3 / 4 / 5 小时的三档）。

## 情景起点的库存（opening inventory）怎么定

- 2023–24 末的净新增 backlog（received − processed）：objections +4,779；
  2024–25 末再 +10,309，累计 +15,088（`appeals_annual_anchor_v3.md` 的 derived 数，
  简单减法，不是公布数）。
- v1 建议：情景在 **2024–25 这 12 个月上做回顾式压力测试**，
  起点 inventory = 4,779（2023–24 末），每月 intake = 当月 monthly_modelled × 0.04（进 B，2026-10-30 定的转移率），
  completions = 9,840 / 9,839（flat），intake × 1.2 跑 12 个月路径。
  这样所有输入都已在库里，不用等 2025–26 的年度数。
- 注意：这是 **B 的库存近似**，不是全口径 backlog——2022–23 的净新增未知
  （processed 空值），且 25% 未进 B 的案子在 A 内如何结案未建模；情景输出必须写清这个限定。

## Day 3 建表时的顺序（建议）

1. 写 `capacity_v1.py`：读 annual_real processed（只取非空的两年）→ flat 拆月 →
   写 capacity_modelled（B，objections）→ 校准检查（每年 completions 合计 = 年度 processed）。
2. 写情景函数（不另建表，先算数）：按上节的起点和公式跑 2024–25 的 12 个月路径，
   输出 backlog 路径 + W + hold-flat FTE（含 3/4/5 小时 sensitivity）。
3. 留待 Liang 确认的两件事：HOURS_PER_CASE_B（4 小时是否合理）、
   Section A 的 capacity 要不要做（要做的话，需另定 triage 每案工时参数，无法用年度数校准）。

## 不做的事

- 不填 2022–23 processed 空值；不用百分比反推。
- 不编 FTE 人数；不把 4 小时 / 140 小时写成 CRA 数据。
- 不把 completions 的 flat 形状说成是 CRA 的办结节奏；它只是 v1 假设。
- 不碰 annual_real、monthly_modelled、cases_modelled、transitions_modelled。
