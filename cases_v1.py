"""Build cases_modelled — one row per Objections processed case (redesign 2026-11-02).

Run from the repo folder (expects appeals.db with monthly_modelled alongside):

    python3 cases_v1.py

WHAT THIS DOES (per Liang 2026-11-02):
  - One row per Objections processed case from monthly_modelled
    (2023-24: 87,543 + 2024-25: 118,077 = 205,620 rows; 2022-23 not built).
  - section = 'Objections' for every row. Columns 'series' and 'completeness'
    dropped.
  - New columns: client_name, group_code, project_code.
  - New column 'litigation' (0/1): each month, exactly round(n*0.04) of that
    month's processed cases are randomly sampled to transfer to Litigation.
  - New columns 'litigation_intake_month' (= processed_month + days_in_litigation)
    and 'days_in_litigation' (uniform 90-365 days, NULL when litigation=0).
    These fold in the old transitions_modelled table, which is dropped here.
  - Fixed RANDOM_SEED so a re-run reproduces the same database.

Distributions (assumptions, not CRA data):
  category: personal_income_tax 50 / corporate 20 / GST-HST 15 /
            benefits_credits_other 15
  complexity: low 30 / medium 50 / high 20
  group_code: uniform over 0001, 0002, 0003
  project_code: uniform over 1000, 1200, 1300, 1700, 1800
  client_name: synthetic sequential IDs (Client-000001, ...), unique
"""

from datetime import date, timedelta
from pathlib import Path
import random
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

RANDOM_SEED = 20261102
TRANSFER_RATE = 0.04          # per month: round(n * 0.04) cases -> litigation
DAYS_MIN, DAYS_MAX = 90, 365  # days from processed month to litigation intake
CATEGORIES = [
    ("personal_income_tax", 0.50),
    ("corporate_income_tax", 0.20),
    ("gst_hst", 0.15),
    ("benefits_credits_other", 0.15),
]
COMPLEXITY = [("low", 0.30), ("medium", 0.50), ("high", 0.20)]
GROUP_CODES = ["0001", "0002", "0003"]
PROJECT_CODES = ["1000", "1200", "1300", "1700", "1800"]

SECTION = "Objections"
SOURCE_TIER = "synthetic_modelled"
METHOD = (
    "synthetic: one row per Objections processed case (monthly_modelled); "
    "section always 'Objections'; category PIT50 CIT20 GST/HST15 benefits+other15; "
    "complexity L30 M50 H20; group_code uniform {0001,0002,0003}; project_code "
    "uniform {1000,1200,1300,1700,1800}; client_name synthetic sequential IDs; "
    "litigation=1 for round(n*0.04) randomly sampled per processed month "
    "(transfer at completion); litigation_intake_month = processed_month + "
    "days_in_litigation (uniform 90-365 days); NULLs when litigation=0 "
    "(assumptions, not CRA data; seed 20261102)."
)


def _pick(rng, weighted):
    x = rng.random()
    acc = 0.0
    for label, share in weighted:
        acc += share
        if x < acc:
            return label
    return weighted[-1][0]


def main() -> None:
    for name, dist in (("CATEGORIES", CATEGORIES), ("COMPLEXITY", COMPLEXITY)):
        assert abs(sum(s for _, s in dist) - 1.0) < 1e-9
    con = sqlite3.connect(DB)
    monthly = con.execute(
        "SELECT fiscal_year, calendar_month, processed_modelled "
        "FROM monthly_modelled WHERE section='Objections' "
        "ORDER BY fiscal_year, calendar_month"
    ).fetchall()
    if not monthly:
        print("monthly_modelled has no Objections rows — run appeals_monthly_modelled_v1.py first.")
        return

    rng = random.Random(RANDOM_SEED)
    con.execute("DROP TABLE IF EXISTS cases_modelled")
    con.execute("DROP TABLE IF EXISTS transitions_modelled")
    con.execute(
        """CREATE TABLE cases_modelled (
  case_id TEXT PRIMARY KEY,
  fiscal_year TEXT,
  processed_month TEXT,
  section TEXT,
  category TEXT,
  complexity TEXT,
  client_name TEXT,
  group_code TEXT,
  project_code TEXT,
  litigation INTEGER,
  litigation_intake_month TEXT,
  days_in_litigation INTEGER,
  source_tier TEXT,
  method TEXT
)"""
    )

    seq, total_lit = 0, 0
    for fy, cal_m, n in monthly:
        y, m = int(cal_m[:4]), int(cal_m[5:7])
        base_day = date(y, m, 1)
        k = round(n * TRANSFER_RATE)
        lit_idx = set(rng.sample(range(n), k)) if k else set()
        total_lit += k
        for i in range(n):
            seq += 1
            litigation = 1 if i in lit_idx else 0
            if litigation:
                days = rng.randint(DAYS_MIN, DAYS_MAX)
                lit_month = (base_day + timedelta(days=days)).strftime("%Y-%m")
            else:
                days, lit_month = None, None
            con.execute(
                "INSERT INTO cases_modelled VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"OB-{seq:06d}", fy, cal_m, SECTION,
                 _pick(rng, CATEGORIES), _pick(rng, COMPLEXITY),
                 f"Client-{seq:06d}",
                 rng.choice(GROUP_CODES), rng.choice(PROJECT_CODES),
                 litigation, lit_month, days, SOURCE_TIER, METHOD),
            )

    # --- calibration checks ---
    expected_total = sum(n for _, _, n in monthly)
    got_total = con.execute("SELECT COUNT(*) FROM cases_modelled").fetchone()[0]
    assert got_total == expected_total, f"{got_total} != {expected_total}"
    print(f"cases: {got_total} (expected {expected_total})")
    for fy, cal_m, n in monthly:
        got = con.execute(
            "SELECT COUNT(*) FROM cases_modelled WHERE processed_month=?",
            (cal_m,)).fetchone()[0]
        assert got == n, f"{cal_m}: {got} != {n}"
    print("check: per-month case counts tie exactly to monthly_modelled;")
    rate = total_lit / got_total
    assert abs(rate - TRANSFER_RATE) < 0.002, f"litigation rate {rate}"
    print(f"check: litigation=1 rows {total_lit} (rate {rate:.4f}, target 0.04);")
    bad_days = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE litigation=1 AND "
        f"(days_in_litigation < {DAYS_MIN} OR days_in_litigation > {DAYS_MAX})"
    ).fetchone()[0]
    assert bad_days == 0
    bad_null = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE "
        "(litigation=0 AND (litigation_intake_month IS NOT NULL OR days_in_litigation IS NOT NULL)) OR "
        "(litigation=1 AND (litigation_intake_month IS NULL OR days_in_litigation IS NULL))"
    ).fetchone()[0]
    assert bad_null == 0
    print("check: days_in_litigation within 90-365 for litigation=1, NULL otherwise;")
    n_sec = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE section != 'Objections'").fetchone()[0]
    assert n_sec == 0
    n_cli = con.execute(
        "SELECT COUNT(DISTINCT client_name) FROM cases_modelled").fetchone()[0]
    assert n_cli == got_total
    print("check: section always 'Objections'; client_name unique;")
    print(f"check: transitions_modelled dropped (folded into cases).")
    con.commit()
    print(f"Wrote {DB} (cases_modelled {got_total} rows)")
    con.close()


if __name__ == "__main__":
    main()
