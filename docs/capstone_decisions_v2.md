# Capstone 参数决策记录 v2（2026-10-30，Liang 确认）

基于 `cases_transitions_design_v1.md` / `capstone_day2_decisions_v1.md` 的待定清单，
Liang 于 2026-10-30 在 side chat 中逐条回复。已锁定的项已进
`cases_transitions_v1.py` 的脚本参数；未锁定的两项（A→B 基准率的合理性、
B 每案工时）等他定后再改。

## 已锁定

1. **Section 定义**：A = Objection，B = Litigation。案子先进入 Objection，
   只有 client 不满意 Objection 结果时才会 process 到 Litigation，
   不是所有 Objection 案子都会进 Litigation。表里永远只存 'A' / 'B'，
   定义写在 method 字段和本文档里。
2. **分布**：category 个税 50% / 企税 20% / GST-HST 15% / 福利抵免及其他 15%；
   complexity low 30 / medium 50 / high 20；completeness 完整 75 / 不完整 25。
3. **A→B 基准转移率**：0.75（已进脚本参数）。
4. **Objection 处理时长**：不固定窗口，按案子在 90–365 天之间变化。
   已进脚本：`_days_in_a` 改为 uniform(90, 365) 整数天；
   校准检查改为 max days ≤ 365。原 180 天固定窗口已废弃。
5. **Section A 的 capacity**：不做。v1 只做 B。

## 已锁定（2026-10-30 第二轮回复）

- **A→B 基准转移率**：0.75 → **0.04**（Liang：0.75 对诉讼来说太高，
  取 0.03–0.05 区间的中点）。已进脚本参数和方法字符串。
- **HOURS_PER_CASE_B**：**4 小时/案**（沿用设计稿推荐值，Liang：用我的建议）。
  情景输出带 3/4/5 小时三档 sensitivity 并标注为假设。
- **EFFECTIVE_HOURS_PER_FTE_MONTH**：**140 小时/人月**（沿用，35 小时/周 × 4 周）。

## 不做的事（沿用 v1）

- 不碰 `annual_real` 和 `monthly_modelled`；不填 2022–23 processed 空值。
- 不把 0.75、类别占比、90–365 天、工时假设写成 CRA 数据；
  只放在脚本参数和 method 字段里。
