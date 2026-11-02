# Intake AI Swarm

WatSPEED Agentic AI course project: an **intake intelligence agent swarm** that answers
operational questions about a case-intake pipeline — volumes, stage transitions,
backlog and staffing — from data, not from the model's imagination.

Every number the swarm reports comes from a deterministic tool. The model explains
results; it never invents arithmetic.

## The five acceptance queries

1. What is the probability that a given case moves from Stage A (Objection) to Stage B (Litigation)?
2. How many cases will Stage B receive next month?
3. Which category is growing fastest?
4. If Stage B intake rises 20%, what happens to backlog and staffing?
5. Produce this week's one-page management briefing.

## Data

`appeals.db` (SQLite) holds three tiers, labelled per row in `source_tier`:

| Tier | Content | Source |
|---|---|---|
| `verified_official` | Annual aggregates (objections received/processed, CPP/EI appeals, taxpayer relief) | CRA Departmental Results Reports (public) |
| `synthetic_modelled` | Monthly intake (108 rows, 2022-04–2025-03), modelled with tax-season weights; case-level rows; transitions | Modelled from the annual anchors — **assumptions, not CRA data** |

No real CRA operational data is used anywhere. All modelling parameters live at the
top of the scripts; change a parameter and re-run.

### Locked modelling parameters (2026-10-30)

- Section A = Objection, Section B = Litigation (tables store only `A`/`B`)
- Category shares: personal income tax 50 / corporate 20 / GST-HST 15 / benefits & credits & other 15
- Complexity low 30 / medium 50 / high 20; completeness complete 75 / incomplete 25
- A→B transfer rate **0.04** (0.75 was judged unrealistic for litigation)
- Objection process duration: uniform **90–365 days** per case
- Section B: **4 hours/case**, **140 effective hours/FTE-month** (scenario assumptions)

See `docs/capstone_decisions_v2.md` for the full decision log.

## Layout

```
├── appeals.db                    # the database (2 tables built; cases/transitions/capacity next)
├── appeals_annual_anchor_v3.csv  # verified annual figures (public)
├── appeals_db_load_v1.py         # builds annual_real
├── appeals_monthly_modelled_v1.py# builds monthly_modelled (108 rows)
├── cases_transitions_v1.py       # builds cases_modelled + transitions_modelled
├── docs/                         # design notes and decision logs
└── concept/                      # submitted project concept (EN v4 / 中文 v5)
```

## Reproduce

Run from this folder, in order (each script is self-contained; the loader rebuilds the DB):

```
python3 appeals_db_load_v1.py
python3 appeals_monthly_modelled_v1.py
python3 cases_transitions_v1.py
```

Each script ends with calibration checks: monthly intake ties exactly to the annual
anchors; yearly case counts tie to `annual_real`; every transition duration is within
90–365 days.

## Status

- Day 1 (2026-10-26): `annual_real` + `monthly_modelled` built and calibrated.
- Day 2 (2026-10-27): cases/transitions script written and tested on a scratch copy;
  parameters locked 2026-10-30.
- Next: capacity table + deterministic tools (transition probability, forecast,
  growth ranking, scenario) → single-agent tool loop → briefing agent → RAG/ChromaDB
  for duplicate detection → Gradio UI → evaluation → progress report (due 2026-11-08).
