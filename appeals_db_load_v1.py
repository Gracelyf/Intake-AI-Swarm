"""Load the verified v3 annual anchor table into appeals.db (Monday starter).

Run from this folder on Mon 2026-10-26 (or copy this script + the CSV to the
project folder first):
    python3 appeals_db_load_v1.py

What it does:
  - Creates appeals.db next to this script (deletes any existing appeals.db
    in the same folder first, so re-running is idempotent).
  - Creates the annual_real table with the schema from
    appeals_annual_anchor_v3.md.
  - Imports appeals_annual_anchor_v3.csv (v1/v2 superseded — do not use them).
  - Blank processed cells become NULL, never 0 and never a back-calculation.

Verified test run 2026-10-25 (Sun) 18:38 ET, in /tmp:
  - 3 rows loaded: 2022-23, 2023-24, 2024-25.
  - 2022-23 objections received = 64,711 (corrected from 64,712 in v2).
  - 2022-23 processed = NULL for objections / CPP-EI / relief — no official
    source was found, and the v3 note forbids filling these in from the
    rounded year-on-year percentages.
  - 2024-25: 128,386 received / 118,077 processed; CPP/EI 2,198 received;
    relief 109,374 received.
  - source_tier preserved per row (2022-23 =
    verified_official_received_only).

Next steps after this load (from v3.md, Mon 2026-10-26 – Thu 2026-10-29):
  1. monthly_modelled — split annual totals across months with the tax-season
     shape, every row flagged synthetic, modelled from published annual totals.
  2. cases / transitions synthetic tables (Section A -> Section B probability).
  3. capacity table (FTEs and monthly completions per section) for the +20%
     scenario tool.
"""
import csv
import pathlib
import sqlite3

BASE = pathlib.Path(__file__).resolve().parent
CSV_PATH = BASE / "appeals_annual_anchor_v3.csv"
DB_PATH = BASE / "appeals.db"

COLS = [
    "fiscal_year",
    "objections_received",
    "objections_processed",
    "cpp_ei_appeals_received",
    "cpp_ei_appeals_processed",
    "taxpayer_relief_received",
    "taxpayer_relief_processed",
    "source_tier",
    "source",
]
INT_COLS = COLS[1:7]


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE annual_real (
  fiscal_year TEXT PRIMARY KEY,
  objections_received INTEGER,
  objections_processed INTEGER,
  cpp_ei_appeals_received INTEGER,
  cpp_ei_appeals_processed INTEGER,
  taxpayer_relief_received INTEGER,
  taxpayer_relief_processed INTEGER,
  source_tier TEXT,
  source TEXT
)"""
    )
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = []
        for row in csv.DictReader(f):
            vals = []
            for c in COLS:
                v = (row[c] or "").strip()
                if c in INT_COLS:
                    vals.append(int(v) if v else None)
                else:
                    vals.append(v)
            rows.append(tuple(vals))
    con.executemany(
        f"INSERT INTO annual_real ({','.join(COLS)}) "
        f"VALUES ({','.join('?' * len(COLS))})",
        rows,
    )
    con.commit()
    for row in con.execute(
        "SELECT fiscal_year, objections_received, objections_processed,"
        " cpp_ei_appeals_received, taxpayer_relief_received"
        " FROM annual_real ORDER BY fiscal_year"
    ):
        print(row)
    print("count:", con.execute("SELECT COUNT(*) FROM annual_real").fetchone()[0])
    con.close()
    print(f"Wrote {DB_PATH} ({len(rows)} rows from {CSV_PATH.name})")


if __name__ == "__main__":
    main()
