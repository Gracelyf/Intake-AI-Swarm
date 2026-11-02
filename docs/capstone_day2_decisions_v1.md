# Capstone Day 2 — 三个待定项的推荐默认值（v1，2026-10-27，为今晚 19:00–21:00 准备）

来源：`cases_transitions_design_v1.md` 的三件事 + concept v1 的验收问题 1。
下面全是 **synthetic_modelled 的脚本参数**，不是 CRA 数据；表里仍只写 Section A / Section B，
不写真实阶段名。Liang 只需回“就按推荐的来”，或改其中任意一行。

## 1. Section A / Section B 指什么

| | 推荐 |
|---|---|
| Section A | 接件与分流：案子已收到、尚未进入实质审理（待分配/待补材料都在 A 里） |
| Section B | 实质审理：已分配、正在审理、走向决定 |

备选：如果他想让 B 更窄，B 可改为“已分配且已开始审理”，A 不变——转移率会相应调低，
见第 3 项。定义一旦定了，今晚建表就不再改。

## 2. Category / complexity / completeness（先只做 objections 系列）

| 字段 | 推荐分布 |
|---|---|
| category | 个人所得税 50% / 企业所得税 20% / GST/HST 15% / 福利与抵免及其他 15% |
| complexity | low 30% / medium 50% / high 20% |
| completeness | complete 75% / incomplete 25% |

为什么这样分：四个类别份额不同，“哪个类别增长最快”（验收问题 3）才有可比性；
份额是演示假设，改参数重跑即可，不影响年度总数校准。
complexity / completeness 是验收问题 1(b) 逻辑回归要用的特征，今晚一并定下来，
免得写脚本时再停。

## 3. A→B 基准转移率与窗口

| | 推荐 |
|---|---|
| 基准转移率 | **0.75**（进入 A 的案子中，75% 在窗口内到达 B） |
| 窗口 | **6 个月** |

为什么是 6 个月：concept v1 验收问题 1(a) 的队列基准率定义就是“过去 6 个月进入 A 的案子
在窗口内到 B 的占比”，窗口取 6 个月与概念稿一致。
备选：窗口 3 个月（信号更快，但转移率要下调到约 0.55–0.65 才合理，因为很多案子
3 个月内还在 A 里排队）。

## 今晚 19:00–21:00 按这个走

1. 他确认上面三行（约 5 分钟，不用 15–20 分钟从头想）。
2. 写 `cases_transitions_v1.py`：参数放脚本顶部；每月进 A 的 synthetic cases 数 =
   当月 `monthly_modelled` 的 objections received_modelled；校准检查：每月 A intake 合计
   = monthly_modelled，A→B 队列率 = 参数值 ± 抽样误差。
3. 剩下的时间写 capacity 表的设计（Day 3 再建）。

## 不做的事

- 不碰 `annual_real` 和 `monthly_modelled`；不填 2022–23 processed 空值。
- 不把上面的 0.75、类别占比写成 CRA 数据；只放在脚本参数和 method 字段里。
