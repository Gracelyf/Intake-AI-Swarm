"""Build the monthly_modelled table in appeals.db — capstone Day 1 (Mon 2026-10-26).

Run from this folder:
    python3 appeals_monthly_modelled_v1.py

What it does:
  - Reads the verified annual totals from annual_real (v3: 2022-23 objections
    received 64,711; 2023-24 87,543; 2024-25 128,386).
  - Splits each fiscal year's RECEIVED total for each series (objections,
    CPP/EI appeals, taxpayer relief) across the 12 fiscal months (Apr-Mar)
    using the MONTHLY_WEIGHTS below, with largest-remainder rounding so the
    12 monthly integers sum EXACTLY to the annual total.
  - Writes monthly_modelled (108 rows = 3 fiscal years x 3 series x 12 months).
  - Re-running is idempotent (drops and rebuilds the table).

WHAT THIS IS NOT: these monthly numbers are NOT CRA data. No monthly CRA
intake figures were found or used. The weights are an explicit modelling
assumption (see below) so the Forecast Agent has a monthly series to work
with; every row is flagged synthetic_modelled. If Liang wants a different
seasonal shape, change MONTHLY_WEIGHTS and re-run — the totals still tie
exactly to the verified annual anchors.

Seasonal-shape assumption (Apr-Mar fiscal year, weights sum to 100):
  Apr  6, May  9, Jun 11, Jul 12, Aug 11, Sep 10,
  Oct  9, Nov  7, Dec  6, Jan  6, Feb  6, Mar  7
  Rationale, stated as assumption only: intake rises after the Apr 30
  personal filing deadline as Notices of Assessment go out, peaks in
  Jun-Aug inside the 90-day objection window, and eases in winter.
  The same shape is applied to all three series for v1 — a deliberate
  simplification, not a claim that relief/CPP-EI follow the same pattern.

NOT built here (on purpose): monthly PROCESSED figures. The 2022-23
processed totals are blank in annual_real (no official source), so there
is nothing to split; processed modelling belongs with the capacity table
(step 3), not here.

Verified test run 2026-10-26 (Mon, in /tmp on a copy of appeals.db):
  - 108 rows written; every fiscal-year x series sum ties exactly to its
    annual_real received total (checked in-script, see --check output).
  - 2022-23 processed columns in annual_real untouched (still NULL).
"""
import pathlib
import sqlite3
import sys

BASE = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE / "appeals.db"

# Fiscal months Apr..Mar, weights in percent (must sum to 100).
MONTHLY_WEIGHTS = [6, 9, 11, 12, 11, 10, 9, 7, 6, 6, 6, 7]
METHOD = (
    "synthetic: annual total split by tax-season weights "
    "Apr6 May9 Jun11 Jul12 Aug11 Sep10 Oct9 Nov7 Dec6 Jan6 Feb6 Mar7 "
    "(assumption, not CRA data); largest-remainder rounding, sums tie exactly"
)

SERIES = [
    ("objections", "objections_received"),
    ("cpp_ei_appeals", "cpp_ei_appeals_received"),
    ("taxpayer_relief", "taxpayer_relief_received"),
]


def split_total(total: int, weights) -> list[int]:
    """Largest-remainder split: integer months summing exactly to total."""
    assert sum(weights) == 100, f"weights sum to {sum(weights)}, not 100"
    raw = [total * w / 100 for w in weights]
    out = [int(x) for x in raw]
    remainder = total - sum(out)
    order = sorted(range(12), key=lambda i: (-(raw[i] - out[i]), i))
    for i in order[:remainder]:
        out[i] += 1
    assert sum(out) == total
    return out


def fiscal_months(fiscal_year: str) -> list[str]:
    """'2024-25' -> ['2024-04', ..., '2025-03'] (Apr-Mar fiscal year)."""
    start = int(fiscal_year.split("-")[0])
    return [f"{start:04d}-{m:02d}" for m in range(4, 13)] + [
        f"{start + 1:04d}-{m:02d}" for m in range(1, 4)
    ]


def main() -> int:
    con = sqlite3.connect(DB_PATH)
    annual = {
        row[0]: row[1:]
        for row in con.execute(
            "SELECT fiscal_year, objections_received,"
            " cpp_ei_appeals_received, taxpayer_relief_received"
            " FROM annual_real ORDER BY fiscal_year"
        )
    }
    if not annual:
        print("annual_real is empty — run appeals_db_load_v1.py first.")
        return 1
    con.execute("DROP TABLE IF EXISTS monthly_modelled")
    con.execute(
        """CREATE TABLE monthly_modelled (
  fiscal_year TEXT,
  month_no INTEGER,
  calendar_month TEXT,
  series TEXT,
  received_modelled INTEGER,
  source_tier TEXT,
  method TEXT,
  PRIMARY KEY (fiscal_year, series, month_no)
)"""
    )
    rows = []
    for fy, totals in annual.items():
        months = fiscal_months(fy)
        for (series, _col), total in zip(SERIES, totals):
            for i, value in enumerate(split_total(total, MONTHLY_WEIGHTS)):
                rows.append(
                    (fy, i + 1, months[i], series, value,
                     "synthetic_modelled", METHOD)
                )
    con.executemany(
        "INSERT INTO monthly_modelled VALUES (?,?,?,?,?,?,?)", rows
    )
    con.commit()
    # Verification: every (fiscal year, series) sum must tie to annual_real.
    bad = []
    for fy, totals in annual.items():
        for (series, _col), total in zip(SERIES, totals):
            got = con.execute(
                "SELECT SUM(received_modelled) FROM monthly_modelled"
                " WHERE fiscal_year=? AND series=?", (fy, series)
            ).fetchone()[0]
            if got != total:
                bad.append((fy, series, total, got))
    count = con.execute("SELECT COUNT(*) FROM monthly_modelled").fetchone()[0]
    print(f"rows: {count} (expected {len(annual) * 3 * 12})")
    for fy in sorted(annual):
        peak = con.execute(
            "SELECT calendar_month, series, received_modelled"
            " FROM monthly_modelled WHERE fiscal_year=? AND month_no=4",
            (fy,),
        ).fetchall()
        print(f"{fy} Jul (peak weight 12%): {peak}")
    if bad:
        print("MISMATCH (should be empty):", bad)
        return 1
    print("check: all monthly sums tie exactly to annual_real received totals.")
    print(f"Wrote {DB_PATH} (monthly_modelled, {count} rows)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
