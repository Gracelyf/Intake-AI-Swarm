"""Build annual_real — objections_processed ONLY (redesign 2026-11-02).

Run from the repo folder (expects appeals_annual_anchor_v3.csv alongside):

    python3 appeals_db_load_v1.py

WHAT THIS DOES:
  Reads appeals_annual_anchor_v3.csv and writes annual_real with exactly
  two columns: fiscal_year + objections_processed.

  Per Liang (2026-11-02): the model only analyzes Litigation, and the only
  useful number from the Objections side is objections_processed. All other
  columns (received, CPP/EI, relief, source_tier, source) are dropped from
  the table. Provenance stays documented in docs/appeals_annual_anchor_v3.md
  and the CSV itself.

  2022-23 processed is NULL (not published; never back-filled).
"""

from pathlib import Path
import csv
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"
CSV = BASE / "appeals_annual_anchor_v3.csv"


def main() -> None:
    con = sqlite3.connect(DB)
    con.execute("DROP TABLE IF EXISTS annual_real")
    con.execute(
        """CREATE TABLE annual_real (
  fiscal_year TEXT PRIMARY KEY,
  objections_processed INTEGER
)"""
    )
    n = 0
    with open(CSV, newline="") as f:
        for row in csv.DictReader(f):
            fy = row["fiscal_year"].strip()
            raw = row["objections_processed"].strip()
            processed = int(raw) if raw else None
            con.execute(
                "INSERT INTO annual_real VALUES (?, ?)", (fy, processed))
            n += 1
    con.commit()
    for fy, p in con.execute(
            "SELECT fiscal_year, objections_processed FROM annual_real ORDER BY fiscal_year"):
        print(f"  {fy}: objections_processed = {p}")
    print(f"Wrote {DB} (annual_real {n} rows: fiscal_year + objections_processed only)")
    con.close()


if __name__ == "__main__":
    main()
