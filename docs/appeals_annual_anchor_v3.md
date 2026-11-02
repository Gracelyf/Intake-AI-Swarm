# Appeals annual anchor table — starter for the capstone data layer (v3)

Prepared 2026-10-25 (Sun afternoon) for the build starting Mon 2026-10-26.
Supersedes v2. This is the `annual_real` table for `appeals.db`: published annual
totals that anchor the synthetic monthly series. No real taxpayer or case-level
data anywhere.

## What changed in v3 (one correction, one verification)

- **2022–23 objections received corrected: 64,712 → 64,711.** The 1-case
  discrepancy flagged in v2 is now resolved: the CRA's own official publication
  gives **64,711** (see Verification below). The 64,712 figure came from a CRA
  email quoted by Investment Executive, which stated the data include objections
  deemed invalid — so the two figures count slightly different things. Use
  64,711 in the anchor table.
- **2022–23 received figures are now verified against an official CRA source.**
  All three received totals (objections, CPP/EI, relief) are now
  `verified_official`. Only the 2022–23 **processed** figures remain blank —
  no official source for them was found, and they are not estimated here.

## The numbers

| Fiscal year | Objections received | Objections processed | CPP/EI appeals received | CPP/EI appeals processed | Relief requests received | Relief requests processed |
|---|---|---|---|---|---|---|
| 2024–25 | 128,386 | 118,077 | 2,198 | 2,127 | 109,374 | 109,329 |
| 2023–24 | 87,543 | 82,764 | 1,705 | 1,785 | 94,180 | 102,498 |
| 2022–23 | 64,711 | — | 1,498 | — | 89,689 | — |

Derived (simple subtraction, received − processed; arithmetic only, not
published figures):
- 2024–25 net backlog added: objections +10,309; CPP/EI +71; relief +45.
- 2023–24 net backlog added: objections +4,779; CPP/EI −80; relief −8,318
  (relief processing cleared more than arrived that year).

## Verification status — read this before citing

- **2024–25 row: verified against the official source.** CRA 2024–25 Departmental
  Results Report, "We provided redress" section (canada.ca). Checked 2026-10-24.
- **2023–24 row: verified against the official source.** CRA 2023–24 Departmental
  Results Report, "At a glance — Providing redress" (canada.ca), checked 2026-10-25:
  87,543 objections received (+35%), 1,705 CPP/EI appeals received (+14%), 94,180
  relief requests received (+5%); 82,764 objections processed (+7%), 1,785 CPP/EI
  appeals processed (+26%), 102,498 relief requests processed (+11%).
  Cross-check: every one of the six 2024–25 reported year-on-year increases
  reproduces exactly from these 2023–24 figures (46.7%→47%, 28.9%→29%,
  16.1%→16%, 42.7%→43%, 19.2%→19%, 6.7%→7%).
- **2022–23 row: received figures NOW VERIFIED against an official CRA source
  (new in v3).** CRA, *Summary of the Corporate Business Plan 2024–25 with
  perspectives to 2026–27* (canada.ca), "Key achievements in 2022–23 —
  Providing redress", checked 2026-10-25: **64,711 objections received,
  1,498 CPP/EI Appeals referred to the Minister, 89,689 Taxpayer relief
  requests received.** This is a CRA publication on canada.ca, not a trade
  press quote — it supersedes the Knowledge Bureau / Moody figures as the
  citation for this row (they agree with it: both gave 64,711 / 1,498 /
  89,689). Cross-check against the 2023–24 reported increases: 87,543 is
  +35.3% over 64,711 (reported +35%); 1,705 is +13.8% over 1,498 (reported
  +14%); 94,180 is +5.0% over 89,689 (reported +5%). Against 2024–25:
  128,386 is +98.4% over 64,711 (reported "up 98%"). All four reproduce.
  - **Why v2 had 64,712:** the CRA email quoted by Investment Executive
    ("Addressing 'technically weak' tax assessments") said 128,386 in 2024–25
    was "up 98% from 64,712 objections in 2022–23", adding "This data include
    objections deemed invalid". Taxpayer Law's 2025-06-17 release gave the
    same 64,712. The 1-case gap (0.0015%) is the invalid-objections counting
    difference; the official published count is 64,711, and that is what the
    table now uses. The percentages cannot distinguish the two (both give
    +98% / +35%), so the tie-breaker is the source: a CRA publication on
    canada.ca outranks a CRA email quoted in trade press.
- **2022–23 processed figures: still NOT verified — do not cite or fill in.**
  The 2022–23 DRR itself (HTML and PDF, checked 2026-10-25) does not carry
  the redress volumes in searchable text; the figures live in the report's
  graphics, which is why the Corporate Business Plan summary (which prints
  them as text) is the citation for the received row. The processed columns
  stay blank. The 2023–24 reported processed increases (+7% / +26% / +11%)
  imply rough 2022–23 processed values (≈77,350 / ≈1,417 / ≈92,340), but
  those are back-calculations from rounded percentages, not published figures
  — they are NOT in the table and must not be cited. The blanks do not block
  the build: the monthly split only needs received totals, and all three
  received totals are now verified official.
- **Not included on purpose:** service-standard / average-days figures (145 /
  403 days, 76% / 71%) were mentioned in earlier chat but were not re-verified
  in this pass, so they are left out. Add them only with a source line each.

## Load it into appeals.db

```sql
CREATE TABLE annual_real (
  fiscal_year TEXT PRIMARY KEY,
  objections_received INTEGER,
  objections_processed INTEGER,
  cpp_ei_appeals_received INTEGER,
  cpp_ei_appeals_processed INTEGER,
  taxpayer_relief_received INTEGER,
  taxpayer_relief_processed INTEGER,
  source_tier TEXT,
  source TEXT
);
```

Then import `appeals_annual_anchor_v3.csv` (same folder; v1 and v2 superseded).
Suggested next steps for the Mon 2026-10-26 – Thu 2026-10-29 data phase, in
order: (1) build `monthly_modelled` by splitting annual totals across months
with the tax-season shape, every row flagged `synthetic, modelled from
published annual totals`; (2) add `cases` / `transitions` synthetic tables for
the Section A → Section B probability question; (3) add a `capacity` table
(FTEs and monthly completions per section) for the +20% scenario tool.

## Sources

- CRA 2024–25 Departmental Results Report:
  https://www.canada.ca/en/revenue-agency/corporate/about-canada-revenue-agency-cra/departmental-performance-reports/2024-25-departmental-results-report.html
- CRA 2023–24 Departmental Results Report, At a glance — Providing redress:
  https://www.canada.ca/en/revenue-agency/corporate/about-canada-revenue-agency-cra/departmental-performance-reports/2023-24-departmental-results-report/at-a-glance.html
- CRA, Summary of the Corporate Business Plan 2024–25 with perspectives to
  2026–27, Key achievements in 2022–23 — Providing redress (new in v3):
  https://www.canada.ca/en/revenue-agency/corporate/about-canada-revenue-agency-cra/summary-corporate-business-plan/summary-cbp-2024-27.html
- Investment Executive, "Addressing 'technically weak' tax assessments"
  (CRA email figures incl. invalid objections — the source of the superseded
  64,712):
  https://www.investmentexecutive.com/news-newspaper/addressing-technically-weak-tax-assessments/
- Taxpayer Law, 2025-06-17:
  https://markets.financialcontent.com/wral/article/prunderground-2025-6-18-surge-in-cra-objections-ends-in-taxpayer-wins-says-cra-lawyers-at-taxpayer-law
- Knowledge Bureau, "Tax Audits are Working for the CRA" (64,711 / 1,498 /
  89,689, citing the CRA departmental report):
  https://www.knowledgebureau.com/site/KBR/tax-audits-are-working-for-the-cra
- Kim G. C. Moody, 2025-07-16 newsletter (64,711):
  https://kimgcmoody.com/kim-g-c-moodys-musings-1-1-1-newsletter-for-july-16-2025/
