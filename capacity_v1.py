"""Build litigation_capacity_modelled — monthly Litigation completions (redesign 2026-11-02).

Run from the repo folder (expects appeals.db with cases_modelled alongside):

    python3 capacity_v1.py

WHAT THIS DOES (per Liang 2026-11-02):
  Writes litigation_capacity_modelled (series column dropped; every row
  section='Litigation'):
      completions_modelled(month)
        = round(0.80 x #{cases_modelled rows with processed_month=month AND litigation=1})
  i.e. each month, 80% of the cases that transferred to Litigation complete —
  "each month's litigation-entering cases have an 80% completion rate".

  Derivation chain (also in every row's method field):
  annual Objections processed (verified) -> monthly processed (seasonal split)
  -> 4%/month randomly sampled to litigation (cases_v1.py) -> 80% complete.

  Drops the old capacity_modelled table.

WHAT THIS IS NOT:
  Published Litigation figures — they do not exist publicly; everything here
  is derived, every step labelled. FTE headcount NOT modelled (NULL).
"""

from pathlib import Path
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

LITIGATION_COMPLETION_RATE = 0.80  # monthly completions = 80% of transferred cases (Liang domain knowledge, 2026-11-02)
HOURS_PER_CASE = 4.0               # avg staff hours per Litigation case (pure assumption)
EFFECTIVE_HOURS_PER_FTE_MONTH = 140.0  # 35 h/week x 4 weeks (pure assumption)

SECTION = "Litigation"
SOURCE_TIER = "synthetic_modelled"
METHOD = (
    "synthetic: monthly Litigation completions = round(0.80 x cases transferred "
    "to Litigation that processed_month). Chain: verified annual Objections "
    "processed -> seasonal monthly split (assumption) -> round(n*0.04)/month "
    "randomly sampled to litigation (cases_v1.py, seed 20261102) -> 80% "
    "completion rate per Liang 2026-11-02 (domain knowledge). No public source "
    "gives Litigation intake/completions. FTE headcount NOT modelled (no "
    "verified source). hours_per_case=4h and effective_hours_per_fte_month=140h "
    "are pure assumptions for the +20% scenario FTE-gap formula, pending "
    "confirmation."
)


def fiscal_year_of(calendar_month: str) -> str:
    y, m = int(calendar_month[:4]), int(calendar_month[5:7])
    if m >= 4:
        return f"{y}-{str(y + 1)[-2:]}"
    return f"{y - 1}-{str(y)[-2:]}"


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT processed_month, COUNT(*) AS n_lit FROM cases_modelled "
        "WHERE litigation=1 GROUP BY processed_month ORDER BY processed_month"
    ).fetchall()
    if not rows:
        print("cases_modelled has no litigation=1 rows — run cases_v1.py first.")
        return

    con.execute("DROP TABLE IF EXISTS capacity_modelled")
    con.execute("DROP TABLE IF EXISTS litigation_capacity_modelled")
    con.execute(
        """CREATE TABLE litigation_capacity_modelled (
  fiscal_year TEXT,
  calendar_month TEXT,
  section TEXT,
  completions_modelled INTEGER,
  fte_modelled REAL,
  hours_per_case REAL,
  effective_hours_per_fte_month REAL,
  source_tier TEXT,
  method TEXT,
  PRIMARY KEY (fiscal_year, section, calendar_month)
)"""
    )
    n_rows = 0
    for r in rows:
        cal_m, n_lit = r["processed_month"], r["n_lit"]
        comp = round(n_lit * LITIGATION_COMPLETION_RATE)
        con.execute(
            "INSERT INTO litigation_capacity_modelled VALUES (?,?,?,?,?,?,?,?,?)",
            (fiscal_year_of(cal_m), cal_m, SECTION, comp, None,
             HOURS_PER_CASE, EFFECTIVE_HOURS_PER_FTE_MONTH,
             SOURCE_TIER, METHOD))
        n_rows += 1

    # --- calibration checks ---
    for r in rows:
        cal_m, n_lit = r["processed_month"], r["n_lit"]
        expected = round(n_lit * LITIGATION_COMPLETION_RATE)
        got = con.execute(
            "SELECT completions_modelled FROM litigation_capacity_modelled "
            "WHERE calendar_month=? AND section=?",
            (cal_m, SECTION)).fetchone()[0]
        assert got == expected, f"{cal_m}: {got} != {expected}"
    n_sec = con.execute(
        "SELECT COUNT(*) FROM litigation_capacity_modelled WHERE section != 'Litigation'"
    ).fetchone()[0]
    assert n_sec == 0
    n_series = con.execute("PRAGMA table_info(litigation_capacity_modelled)").fetchall()
    assert not any(c[1] == "series" for c in n_series), "series column must be gone"
    total = con.execute(
        "SELECT SUM(completions_modelled) FROM litigation_capacity_modelled").fetchone()[0]
    print(f"check: {n_rows} months, every completions_modelled = round(0.80 x transferred);")
    print(f"check: section all 'Litigation', no series column; total = {total}.")
    con.commit()
    print(f"Wrote {DB} (litigation_capacity_modelled {n_rows} rows)")
    print(f"params: litigation_completion_rate={LITIGATION_COMPLETION_RATE}, "
          f"hours_per_case={HOURS_PER_CASE}, "
          f"effective_hours_per_fte_month={EFFECTIVE_HOURS_PER_FTE_MONTH}")
    con.close()


if __name__ == "__main__":
    main()
