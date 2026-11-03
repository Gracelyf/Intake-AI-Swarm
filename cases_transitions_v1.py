"""Build cases_modelled + transitions_modelled in appeals.db — capstone Day 2 (Tue 2026-10-27).

Run from this folder:
    python3 cases_transitions_v1.py

What it does:
  - Reads the monthly objections intake from monthly_modelled (Day 1 output,
    synthetic_modelled) and generates one synthetic case per received objection.
  - Writes cases_modelled (one row per case) and transitions_modelled
    (one row per case that moves A -> B).
  - Re-running is idempotent (drops and rebuilds both tables).

Parameters — all from capstone_day2_decisions_v1.md (2026-10-27), updated with
Liang's locked decisions 2026-10-30 (see capstone_decisions_v2.md). These are
SCRIPT PARAMETERS, not CRA data. Change them at the top and re-run; the
calibration checks below still have to pass. Liang only needs to confirm
(or edit) these lines before running tonight:
  - Section A = Objection (received, not yet escalated); Section B = Litigation
    (escalated by the client after an unsatisfactory Objection outcome — not
    every Objections case proceeds to Litigation with probability 0.04).
    Tables store 'Objections' / 'Litigation' (CRA stage names); the real-stage
    names live in this docstring and in capstone_decisions_v2.md.
  - Categories (objections only for v1): personal income tax 50% /
    corporate income tax 20% / GST/HST 15% / benefits & credits + other 15%.
  - Complexity: low 30% / medium 50% / high 20%.
  - Completeness: complete 75% / incomplete 25%.
  - A->B base transfer rate 0.04 (Liang 2026-10-30: 0.75 unrealistic for
    litigation; set to the 0.03-0.05 range midpoint), per-case Objection process
    duration uniform 90-365 days. This matches concept v1 acceptance-test
    Q1(a): share of cases entering A that reach B.

WHAT THIS IS NOT: no case here is a real CRA case. Case IDs are SYN-...,
every row is flagged synthetic_modelled, and the category / complexity /
completeness / transfer figures are explicit modelling assumptions.
Monthly A intake still ties EXACTLY to monthly_modelled, which ties exactly
to the verified annual_real received totals — no new intake total is invented.

NOT built here (on purpose): monthly PROCESSED figures, and the capacity
table (step 3, Day 3). The 2022-23 processed total in annual_real is still
blank (no official source) and is not touched.

Test run 2026-10-27 (in /tmp on a copy of appeals.db — real DB untouched,
with the OLD parameters: rate 0.75, 180-day window):
  - cases: 280,640 (2022-23: 64,711; 2023-24: 87,543; 2024-25: 128,386)
  - transitions: 210,710 (75.08% of cases — parameter 0.75 +/- sampling error)
  - monthly A intake ties exactly to monthly_modelled objections, every month
  - every transition lands within 180 days of intake (max days_in_from_section 180)
  - annual_real and monthly_modelled untouched; 2022-23 processed still NULL
"""

import datetime as _dt
import pathlib
import random
import sqlite3
import sys

BASE = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE / "appeals.db"

# --- Decisions to confirm (capstone_day2_decisions_v1.md) -------------------
RANDOM_SEED = 20261027
TRANSFER_RATE = 0.04          # share of A (Objection) cases that proceed to B (Litigation);
                              # Liang 2026-10-30: 0.75 unrealistic for litigation, set to 0.03-0.05 range -> midpoint 0.04
DAYS_MIN = 90                 # per-case Objection process duration varies 90-365 days
DAYS_MAX = 365
# Days a transferring case spends in A: uniform 90-365 (Objection process
# duration; Liang 2026-10-30). A transferring case leaves A on a date that may
# fall beyond the old 180-day window; calibration check asserts max <= 365.
CATEGORIES = [  # (label, share) — shares must sum to 1.0
    ("personal_income_tax", 0.50),
    ("corporate_income_tax", 0.20),
    ("gst_hst", 0.15),
    ("benefits_credits_other", 0.15),
]
COMPLEXITY = [("low", 0.30), ("medium", 0.50), ("high", 0.20)]
COMPLETENESS = [("complete", 0.75), ("incomplete", 0.25)]
METHOD = (
    "synthetic: Section A=Objection, Section B=Litigation (not all Objection "
    "cases proceed to Litigation); category PIT50 CIT20 GST/HST15 benefits+other15; "
    "complexity L30 M50 H20; completeness complete75 incomplete25; A->B rate 0.04; "
    "Objection process duration uniform 90-365 days per case "
    "(assumptions, not CRA data); monthly A intake = monthly_modelled objections"
)
SECTION_A = "Objections"   # tables store CRA stage names (renamed 2026-11-02)
SECTION_B = "Litigation"   # (see decisions file for the definitions)


def _pick(rng, weighted):
    x = rng.random()
    acc = 0.0
    for label, share in weighted:
        acc += share
        if x < acc:
            return label
    return weighted[-1][0]


def _days_in_a(rng):
    # Objection process duration varies by case: uniform 90-365 days (Liang, 2026-10-30)
    return rng.randint(DAYS_MIN, DAYS_MAX)


def main() -> int:
    for name, dist in (("CATEGORIES", CATEGORIES), ("COMPLEXITY", COMPLEXITY),
                       ("COMPLETENESS", COMPLETENESS)):
        assert abs(sum(s for _, s in dist) - 1.0) < 1e-9, f"{name} shares != 1.0"
    assert 0.0 < TRANSFER_RATE < 1.0

    con = sqlite3.connect(DB_PATH)
    monthly = con.execute(
        "SELECT fiscal_year, calendar_month, received_modelled"
        " FROM monthly_modelled WHERE series='objections'"
        " ORDER BY fiscal_year, calendar_month"
    ).fetchall()
    if not monthly:
        print("monthly_modelled has no objections rows — run appeals_monthly_modelled_v1.py first.")
        return 1

    rng = random.Random(RANDOM_SEED)
    con.execute("DROP TABLE IF EXISTS cases_modelled")
    con.execute("DROP TABLE IF EXISTS transitions_modelled")
    con.execute(
        """CREATE TABLE cases_modelled (
  case_id TEXT PRIMARY KEY,
  fiscal_year TEXT,
  intake_month TEXT,
  series TEXT,
  section TEXT,
  category TEXT,
  complexity TEXT,
  completeness TEXT,
  source_tier TEXT,
  method TEXT
)"""
    )
    con.execute(
        """CREATE TABLE transitions_modelled (
  case_id TEXT,
  from_section TEXT,
  to_section TEXT,
  transition_month TEXT,
  days_in_from_section INTEGER,
  source_tier TEXT,
  method TEXT,
  PRIMARY KEY (case_id, from_section, to_section)
)"""
    )

    case_rows, trans_rows = [], []
    seq = {}
    for fy, intake_month, n in monthly:
        seq.setdefault(fy, 0)
        year, month = int(intake_month[:4]), int(intake_month[5:7])
        intake_date = _dt.date(year, month, 1)
        for _ in range(n):
            seq[fy] += 1
            case_id = f"SYN-{fy}-{seq[fy]:06d}"
            category = _pick(rng, CATEGORIES)
            complexity = _pick(rng, COMPLEXITY)
            completeness = _pick(rng, COMPLETENESS)
            if rng.random() < TRANSFER_RATE:
                section = SECTION_B
                days = _days_in_a(rng)
                trans_month = (intake_date + _dt.timedelta(days=days)).strftime("%Y-%m")
                trans_rows.append(
                    (case_id, "Objections", "Litigation", trans_month, days, "synthetic_modelled", METHOD)
                )
            else:
                section = SECTION_A
            case_rows.append(
                (case_id, fy, intake_month, "objections", section, category,
                 complexity, completeness, "synthetic_modelled", METHOD)
            )

    con.executemany("INSERT INTO cases_modelled VALUES (?,?,?,?,?,?,?,?,?,?)", case_rows)
    con.executemany("INSERT INTO transitions_modelled VALUES (?,?,?,?,?,?,?)", trans_rows)
    con.commit()

    # --- Calibration checks (same discipline as Day 1) -----------------------
    bad = []
    n_cases = con.execute("SELECT COUNT(*) FROM cases_modelled").fetchone()[0]
    n_trans = con.execute("SELECT COUNT(*) FROM transitions_modelled").fetchone()[0]
    for fy, intake_month, n in monthly:
        got = con.execute(
            "SELECT COUNT(*) FROM cases_modelled"
            " WHERE fiscal_year=? AND intake_month=?", (fy, intake_month)
        ).fetchone()[0]
        if got != n:
            bad.append((fy, intake_month, n, got))
    annual = dict(con.execute(
        "SELECT fiscal_year, objections_received FROM annual_real"
    ).fetchall())
    for fy, total in annual.items():
        got = con.execute(
            "SELECT COUNT(*) FROM cases_modelled WHERE fiscal_year=?", (fy,)
        ).fetchone()[0]
        if got != total:
            bad.append((fy, "annual", total, got))
    max_days = con.execute(
        "SELECT MAX(days_in_from_section) FROM transitions_modelled"
    ).fetchone()[0]
    if max_days > DAYS_MAX:
        bad.append(("max_days", max_days))
    rate = n_trans / n_cases if n_cases else 0
    print(f"cases: {n_cases} (expected {sum(annual.values())})")
    for fy in sorted(annual):
        print(f"  {fy}: {con.execute('SELECT COUNT(*) FROM cases_modelled WHERE fiscal_year=?', (fy,)).fetchone()[0]} (annual_real {annual[fy]})")
    print(f"transitions: {n_trans} — A->B rate {rate:.4f} (parameter {TRANSFER_RATE})")
    print(f"max days in A: {max_days} (allowed {DAYS_MIN}-{DAYS_MAX})")
    print("category shares:",
          {r[0]: round(r[1] / n_cases, 3) for r in con.execute(
              "SELECT category, COUNT(*) FROM cases_modelled GROUP BY category").fetchall()})
    if bad:
        print("MISMATCH (should be empty):", bad)
        return 1
    print("check: monthly A intake ties exactly to monthly_modelled objections;")
    print("check: annual case counts tie exactly to annual_real objections received;")
    print("check: every transition duration is within 90-365 days.")
    print(f"Wrote {DB_PATH} (cases_modelled {n_cases} rows, "
          f"transitions_modelled {n_trans} rows)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
