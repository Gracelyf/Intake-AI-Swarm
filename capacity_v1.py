"""Build the capacity_modelled table in appeals.db — capstone Day 3 (Sun 2026-11-01).

Run from the repo folder (expects appeals.db alongside this script):

    python3 capacity_v1.py

WHAT THIS DOES:
  - Reads annual_real objections PROCESSED for the two fiscal years that have
    verified values (2023-24: 82,764; 2024-25: 118,077; CRA Departmental
    Results Reports).
  - Splits each annual processed total FLAT across the 12 fiscal months
    (Apr-Mar), largest-remainder so monthly integers sum EXACTLY to the
    annual total. 118,077 / 12 = 9 x 9840 + 3 x 9839; 82,764 / 12 = 6897 exact.
  - Writes capacity_modelled: Section B, objections series only (v1).

WHAT THIS IS NOT:
  - Flat monthly completions are a modelling ASSUMPTION, not CRA data.
    Completions are staff output and smoother than intake; the flat shape lets
    backlog accumulate in intake peak months (e.g. July) and clear in trough
    months, which is what the +20% scenario needs. Shape is a parameter —
    change it and re-run.
  - 2022-23 is NOT built: processed is NULL in annual_real (no official
    source; v3 anchor explicitly warns against back-filling from rounded
    percentages). Completions stay missing for that year.
  - Section A is NOT built: annual processed is a single total, not split by
    section, so A cannot be calibrated the same way. v1 is B only (the +20%
    scenario asks about B).
  - FTE headcount is NOT modelled (fte_modelled = NULL): no verified FTE
    source, so no headcount numbers are invented. The FTE gap is computed by
    formula in the scenario tool, not from a stored headcount.

PARAMETERS (all assumptions, not CRA data — change and re-run):
"""

from pathlib import Path
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

# --- v1 parameters (pure assumptions; pending Liang's confirmation) ---
COMPLETIONS_SHAPE = "flat"          # "flat" = equal monthly split
HOURS_PER_CASE_B = 4.0              # avg staff hours per Section B case
EFFECTIVE_HOURS_PER_FTE_MONTH = 140.0  # 35 h/week x 4 weeks

SECTION = "A"
SERIES = "objections"
SOURCE_TIER = "synthetic_modelled"

METHOD = (
    "v1: Section A (Objection stage) monthly completions split FLAT from verified annual "
    "processed (2023-24: 82764; 2024-25: 118077; CRA Departmental Results "
    "Reports; objections processed = Section A outflow, confirmed 2026-11-02). Section B completions NOT in this table. Flat monthly shape is a modelling assumption, not CRA data. "
    "2022-23 not built (processed NULL, no official source). FTE headcount "
    "NOT modelled (no verified source). hours_per_case=4h and "
    "effective_hours_per_fte_month=140h are pure assumptions for the +20% "
    "scenario FTE-gap formula (extra cases x hours per case / effective "
    "hours), pending confirmation."
)


def fiscal_months(fiscal_year: str) -> list:
    """'2024-25' -> ['2024-04', ..., '2025-03'] (Apr-Mar fiscal year)."""
    start = int(fiscal_year.split("-")[0])
    return [f"{start + (m > 12):04d}-{((m - 1) % 12) + 1:02d}"
            for m in range(4, 16)]


def flat_split(total: int, n: int = 12) -> list:
    """Largest-remainder split: n integer months summing exactly to total."""
    base, rem = divmod(total, n)
    return [base + 1 if i < rem else base for i in range(n)]


def main() -> None:
    assert COMPLETIONS_SHAPE == "flat", "v1 only supports flat split"
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT fiscal_year, objections_processed FROM annual_real "
        "WHERE objections_processed IS NOT NULL ORDER BY fiscal_year"
    ).fetchall()
    assert rows, "annual_real has no processed rows"

    con.execute("DROP TABLE IF EXISTS capacity_modelled")
    con.execute(
        """CREATE TABLE capacity_modelled (
  fiscal_year TEXT,
  calendar_month TEXT,
  series TEXT,
  section TEXT,
  completions_modelled INTEGER,
  fte_modelled REAL,
  hours_per_case REAL,
  effective_hours_per_fte_month REAL,
  source_tier TEXT,
  method TEXT,
  PRIMARY KEY (fiscal_year, series, section, calendar_month)
)"""
    )

    n_rows = 0
    for r in rows:
        fy, total = r["fiscal_year"], r["objections_processed"]
        months = fiscal_months(fy)
        assert len(months) == 12
        splits = flat_split(total)
        assert sum(splits) == total, f"{fy}: monthly sum != annual total"
        for cal_m, comp in zip(months, splits):
            con.execute(
                "INSERT INTO capacity_modelled VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fy, cal_m, SERIES, SECTION, comp, None,
                 HOURS_PER_CASE_B, EFFECTIVE_HOURS_PER_FTE_MONTH,
                 SOURCE_TIER, METHOD),
            )
            n_rows += 1

    # --- calibration checks ---
    for r in rows:
        fy, total = r["fiscal_year"], r["objections_processed"]
        got = con.execute(
            "SELECT SUM(completions_modelled) FROM capacity_modelled "
            "WHERE fiscal_year=? AND series=? AND section=?",
            (fy, SERIES, SECTION),
        ).fetchone()[0]
        assert got == total, f"{fy}: {got} != {total}"
        print(f"  {fy}: monthly completions sum {got} (annual processed {total})")

    n_2223 = con.execute(
        "SELECT COUNT(*) FROM capacity_modelled WHERE fiscal_year='2022-23'"
    ).fetchone()[0]
    assert n_2223 == 0, "2022-23 must stay missing (processed NULL)"
    n_a = con.execute(
        "SELECT COUNT(*) FROM capacity_modelled WHERE section='B'"
    ).fetchone()[0]
    assert n_a == 0, "v1 is Section A only"

    con.commit()
    print(f"Wrote {DB} (capacity_modelled {n_rows} rows: "
          f"{len(rows)} fiscal years x 12 months, Section A objections)")
    print(f"params: hours_per_case={HOURS_PER_CASE_B}, "
          f"effective_hours_per_fte_month={EFFECTIVE_HOURS_PER_FTE_MONTH}, "
          f"fte_modelled=NULL")
    con.close()


if __name__ == "__main__":
    main()
