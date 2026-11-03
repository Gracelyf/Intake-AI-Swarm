"""Build monthly_modelled — monthly Objections PROCESSED (redesign 2026-11-02).

Run from the repo folder (expects appeals.db alongside):

    python3 appeals_monthly_modelled_v1.py

WHAT THIS DOES:
  Splits each fiscal year's objections_processed (annual_real) across the
  12 fiscal months (Apr-Mar) using tax-season weights, so the months have
  fluctuation and a peak month (July), while the 12 monthly integers sum
  EXACTLY to the annual total (largest-remainder).

  Per Liang (2026-11-02):
  - monthly values come from annual objections_processed (NOT received);
  - column 'series' renamed to 'section', only 'Objections' rows;
  - monthly fluctuation + peak month required; annual totals must tie.

  2022-23 NOT built: objections_processed is NULL (not published).

Seasonal-shape assumption (Apr-Mar fiscal year, weights sum to 100):
  Apr 6, May 9, Jun 11, Jul 12, Aug 11, Sep 10, Oct 9,
  Nov 7, Dec 6, Jan 6, Feb 6, Mar 7.
  This shape is an ASSUMPTION, not CRA data (no monthly source exists).
"""

from pathlib import Path
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

# Fiscal months Apr..Mar, weights in percent (must sum to 100).
WEIGHTS = [6, 9, 11, 12, 11, 10, 9, 7, 6, 6, 6, 7]
assert sum(WEIGHTS) == 100

SECTION = "Objections"
SOURCE_TIER = "synthetic_modelled"
METHOD = (
    "synthetic: annual Objections processed split by tax-season weights "
    "Apr6 May9 Jun11 Jul12 Aug11 Sep10 Oct9 Nov7 Dec6 Jan6 Feb6 Mar7 "
    "(assumption, not CRA data — no monthly source exists); largest-remainder "
    "rounding, monthly sums tie exactly to annual processed. 2022-23 not "
    "built (processed NULL, not published)."
)


def fiscal_months(fiscal_year: str) -> list:
    """'2024-25' -> ['2024-04', ..., '2025-03'] (Apr-Mar fiscal year)."""
    start = int(fiscal_year.split("-")[0])
    return [f"{start + (m > 12):04d}-{((m - 1) % 12) + 1:02d}"
            for m in range(4, 16)]


def weighted_split(total: int, weights: list) -> list:
    """Largest-remainder split: integer months summing exactly to total."""
    exact = [total * w / 100 for w in weights]
    base = [int(x) for x in exact]
    remainder = total - sum(base)
    order = sorted(range(len(weights)),
                   key=lambda i: exact[i] - base[i], reverse=True)
    for i in order[:remainder]:
        base[i] += 1
    assert sum(base) == total
    return base


def main() -> None:
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT fiscal_year, objections_processed FROM annual_real "
        "WHERE objections_processed IS NOT NULL ORDER BY fiscal_year"
    ).fetchall()
    assert rows, "annual_real has no processed rows"

    con.execute("DROP TABLE IF EXISTS monthly_modelled")
    con.execute(
        """CREATE TABLE monthly_modelled (
  fiscal_year TEXT,
  month_no INTEGER,
  calendar_month TEXT,
  section TEXT,
  processed_modelled INTEGER,
  source_tier TEXT,
  method TEXT,
  PRIMARY KEY (fiscal_year, section, month_no)
)"""
    )
    n_rows = 0
    for fy, total in rows:
        months = fiscal_months(fy)
        splits = weighted_split(total, WEIGHTS)
        for i, (cal_m, val) in enumerate(zip(months, splits), start=1):
            con.execute(
                "INSERT INTO monthly_modelled VALUES (?,?,?,?,?,?,?)",
                (fy, i, cal_m, SECTION, val, SOURCE_TIER, METHOD))
            n_rows += 1
        peak = months[splits.index(max(splits))]
        print(f"  {fy}: monthly processed sum {sum(splits)} "
              f"(annual {total}), peak {peak} = {max(splits)}")
    con.commit()
    print(f"Wrote {DB} (monthly_modelled {n_rows} rows: "
          f"{len(rows)} fiscal years x 12 months, section=Objections)")
    con.close()


if __name__ == "__main__":
    main()
