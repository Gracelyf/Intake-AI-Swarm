# Capstone Day 2 — cases / transitions 表设计（v1，2026-10-26 晚，为周二 10/27 19:00–21:00 的 AI project 时段准备）

Day 1 已完成：`monthly_modelled` 108 行进 `appeals.db`，每年合计与已核过的年度数严丝合缝
（2024–25 objections 合计 128,386，峰值 2024 年 7 月 15,406；月度数是 synthetic_modelled，不是 CRA 数据）。
按 v3 文档的顺序，下一步就是 cases / transitions 表，再往后是 capacity 表。

## 这张表要回答的问题（concept v1 验收问题 1）

> What is the probability that a given case moves from Section A to Section B?

分两层（concept v1 已定）：(a) 队列基准率——过去 6 个月进入 Section A 的案子中，在设定窗口内到达 Section B 的占比；
(b) 个案调整——按 category / complexity / completeness 做逻辑回归，给出带区间的估计和前 2–3 个驱动因素。
未知 case ID 只问澄清，绝不编一个案子出来。

## 建议的表结构（不改 annual_real / monthly_modelled）

```sql
CREATE TABLE cases_modelled (
  case_id TEXT PRIMARY KEY,          -- synthetic，如 SYN-2024-000001
  fiscal_year TEXT,                  -- '2024-25'
  intake_month TEXT,                 -- '2024-07'，与 monthly_modelled.calendar_month 对齐
  series TEXT,                       -- 'objections' 起步；CPP/EI、relief 后加
  section TEXT,                      -- 'A' / 'B'（当前所在阶段）
  category TEXT,                     -- 待定：见下
  complexity TEXT,                   -- 'low' / 'medium' / 'high'（待定）
  completeness TEXT,                 -- 'complete' / 'incomplete'（待定）
  source_tier TEXT,                  -- 'synthetic_modelled'
  method TEXT
);

CREATE TABLE transitions_modelled (
  case_id TEXT,
  from_section TEXT,                 -- 'A'
  to_section TEXT,                   -- 'B'
  transition_month TEXT,
  days_in_from_section INTEGER,
  source_tier TEXT,                  -- 'synthetic_modelled'
  method TEXT,
  PRIMARY KEY (case_id, from_section, to_section)
);
```

## 校准规则（Day 1 同款做法：总数必须严丝合缝）

- 每月进入 Section A 的 synthetic cases 数 = 当月 `monthly_modelled` 的 objections received_modelled。
  这样 cases 表加总回去正好是年度已核数（2024–25：128,386），不另外编 intake 总量。
- A→B 的转移率、category 分布、complexity 分布、停留天数分布，全部写成脚本顶部的显式参数
  （像 Day 1 的 MONTHLY_WEIGHTS 一样），改参数重跑即可，表里每行标 synthetic_modelled。
- 2022–23 的 processed 仍是空值（无官方来源），不要从百分比反推去填——capacity 表再处理。

## Day 2 开始前要 Liang 定的三件事（concept v1 的 open item，至今未确认）

1. **Section A / Section B 到底指什么阶段？** concept 里写的是 anonymised stage labels，
   一直没确认定义。先定这个，再定转移率，否则数字没有意义。
2. **Category 清单**：用哪几个类别（例如按税种 / 争议类型）？以及各类别占比是均分还是另有假设。
3. **转移率初值**：A→B 的基准率先设多少（例如先跑一个参数，看队列基准率是否合理），
   以及“在窗口内到达 B”的窗口是几个月（3 个月 / 6 个月）。

## 明晚 19:00–21:00 的建议顺序

1. 定上面三件事（15–20 分钟，口头定就行）。
2. 按本文件写 `cases_transitions_v1.py`：读 monthly_modelled → 生成 cases + transitions → 跑校准检查
   （每月 A intake 合计 = monthly_modelled；A→B 队列率 = 参数值 ± 抽样误差）。
3. 留 20 分钟写 capacity 表的设计（FTE 与每月 completions），Day 3 再建。

## 不做的事

- 不碰 `annual_real` 和 `monthly_modelled`；不填 2022–23 processed 空值。
- 不把 synthetic 的转移率、类别占比写成 CRA 数据；所有假设只放在脚本参数和 method 字段里。
