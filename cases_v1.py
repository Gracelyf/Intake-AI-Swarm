"""Build cases_modelled — one row per Objections processed case (redesign 2026-11-02).

Run from the repo folder (expects appeals.db with monthly_modelled alongside):

    python3 cases_v1.py

WHAT THIS DOES (per Liang 2026-11-02, amended same evening):
  - One row per Objections processed case from monthly_modelled
    (2023-24: 82,764 + 2024-25: 118,077 = 200,841 rows; 2022-23 not built).
  - Two ID columns: objections_case_id ("OB-000001", every row, PRIMARY KEY)
    and litigation_case_id ("LIT-000001", only rows with litigation=1, in
    litigation_intake_month order; NULL otherwise).
  - client_name: realistic-looking "First Last" names (English, French, and
    common immigrant-origin names reflecting Canadian diversity). Synthetic —
    duplicates expected, one client may have several cases.
  - section = 'Objections' for every row. Columns 'series' and 'completeness'
    dropped.
  - New columns: group_code (0001/0002/0003), project_code
    (1000/1200/1300/1700/1800).
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
"""

from datetime import date, timedelta
from pathlib import Path
import math
import random
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

RANDOM_SEED = 20261102
AMOUNT_SEED = RANDOM_SEED + 1000  # separate RNG stream for amounts: existing
                                  # columns stay bit-identical when amounts
                                  # are added/changed
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
# amount_involved (CAD): lognormal per category — tax disputes are heavy-tailed
# (many small, few huge). Medians are PURE ASSUMPTIONS, not CRA data.
AMOUNT_MEDIAN = {
    "personal_income_tax": 8000,
    "corporate_income_tax": 60000,
    "gst_hst": 15000,
    "benefits_credits_other": 3000,
}
AMOUNT_SIGMA = 1.2  # lognormal sigma (tail weight), pure assumption

# Synthetic name pools (Canadian mix: English, French, South/East Asian,
# Middle Eastern, Latin American). Names are fiction; duplicates expected.
FIRST_NAMES = [
    "James", "Mary", "Robert", "Jennifer", "Michael", "Linda", "William",
    "Sarah", "David", "Emma", "Richard", "Olivia", "Thomas", "Sophia",
    "Charles", "Ava", "Daniel", "Emily", "Matthew", "Chloe", "Liam",
    "Noah", "Lucas", "Ethan", "Oliver", "Elijah", "Benjamin", "Harper",
    "Evelyn", "Abigail", "Ella", "Scarlett", "Grace", "Victoria", "Lily",
    "Aria", "Zoey", "Nora", "Hazel", "Stella", "Jean", "Pierre", "Marie",
    "François", "Sophie", "Isabelle", "Michel", "André", "Nicole",
    "Claude", "Diane", "Julien", "Camille", "Laurent", "Sylvie", "Raj",
    "Priya", "Amit", "Arjun", "Ananya", "Vikram", "Meera", "Rohan",
    "Divya", "Wei", "Fang", "Lei", "Min", "Jing", "Tao", "Ahmed",
    "Fatima", "Omar", "Hassan", "Aisha", "Yusuf",
]
LAST_NAMES = [
    "Smith", "Johnson", "Brown", "Taylor", "Miller", "Davis", "Wilson",
    "Moore", "Clark", "Lewis", "Walker", "Hall", "Young", "King",
    "Wright", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter",
    "Mitchell", "Roberts", "Turner", "Phillips", "Campbell", "Parker",
    "Evans", "Edwards", "Collins", "Stewart", "Morris", "Rogers", "Reed",
    "Cook", "Morgan", "Bell", "Murphy", "Bailey", "Rivera", "Cooper",
    "Richardson", "Cox", "Howard", "Ward", "Tremblay", "Gagnon", "Roy",
    "Côté", "Bouchard", "Gauthier", "Lavoie", "Fortin", "Morin",
    "Pelletier", "Bélanger", "Lévesque", "Singh", "Kaur", "Patel",
    "Sharma", "Gupta", "Khan", "Chen", "Wang", "Li", "Zhang", "Liu",
    "Yang", "Huang", "Xu", "Zhao", "Wu", "Nguyen", "Tran", "Kim",
    "Park", "Wong", "Garcia", "Martinez", "Ahmed", "Hassan", "Ali",
]

SECTION = "Objections"
SOURCE_TIER = "synthetic_modelled"
METHOD = (
    "synthetic: one row per Objections processed case (monthly_modelled); "
    "objections_case_id for all rows (PK), litigation_case_id only when "
    "litigation=1 (in litigation_intake_month order); section always "
    "'Objections'; client_name = synthetic 'First Last' (fictional, "
    "duplicates expected); category PIT50 CIT20 GST/HST15 benefits+other15; "
    "complexity L30 M50 H20; group_code uniform {0001,0002,0003}; project_code "
    "uniform {1000,1200,1300,1700,1800}; litigation=1 for round(n*0.04) "
    "randomly sampled per processed month (transfer at completion); "
    "litigation_intake_month = processed_month + days_in_litigation (uniform "
    "90-365 days); amount_involved (CAD, integer dollars) lognormal per "
    "category, medians PIT 8000 / CIT 60000 / GST-HST 15000 / benefits+other "
    "3000, sigma 1.2 (heavy tail — pure assumptions, not CRA data); NULLs "
    "when litigation=0 (assumptions, not CRA data; "
    "seed 20261102, amounts on separate stream seed 20262102)."
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
    amount_rng = random.Random(AMOUNT_SEED)  # separate stream: adding amounts
                                            # never changes existing columns

    # --- pass 1: generate rows ---
    rows = []
    seq = 0
    for fy, cal_m, n in monthly:
        y, m = int(cal_m[:4]), int(cal_m[5:7])
        base_day = date(y, m, 1)
        k = round(n * TRANSFER_RATE)
        lit_idx = set(rng.sample(range(n), k)) if k else set()
        for i in range(n):
            seq += 1
            litigation = 1 if i in lit_idx else 0
            if litigation:
                days = rng.randint(DAYS_MIN, DAYS_MAX)
                lit_month = (base_day + timedelta(days=days)).strftime("%Y-%m")
            else:
                days, lit_month = None, None
            category = _pick(rng, CATEGORIES)
            amount = max(1, int(amount_rng.lognormvariate(
                math.log(AMOUNT_MEDIAN[category]), AMOUNT_SIGMA)))
            rows.append({
                "objections_case_id": f"OB-{seq:06d}",
                "litigation_case_id": None,  # assigned in pass 2
                "fiscal_year": fy,
                "processed_month": cal_m,
                "section": SECTION,
                "category": category,
                "complexity": _pick(rng, COMPLEXITY),
                "client_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "group_code": rng.choice(GROUP_CODES),
                "project_code": rng.choice(PROJECT_CODES),
                "litigation": litigation,
                "litigation_intake_month": lit_month,
                "days_in_litigation": days,
                "amount_involved": amount,
            })

    # --- pass 2: assign litigation IDs in intake-month order ---
    lit_rows = sorted(
        (r for r in rows if r["litigation"]),
        key=lambda r: (r["litigation_intake_month"], r["objections_case_id"]))
    for n, r in enumerate(lit_rows, start=1):
        r["litigation_case_id"] = f"LIT-{n:06d}"

    con.execute("DROP TABLE IF EXISTS cases_modelled")
    con.execute("DROP TABLE IF EXISTS transitions_modelled")
    con.execute(
        """CREATE TABLE cases_modelled (
  objections_case_id TEXT PRIMARY KEY,
  litigation_case_id TEXT,
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
  amount_involved INTEGER,
  source_tier TEXT,
  method TEXT
)"""
    )
    for r in rows:
        con.execute(
            "INSERT INTO cases_modelled VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["objections_case_id"], r["litigation_case_id"], r["fiscal_year"],
             r["processed_month"], r["section"], r["category"], r["complexity"],
             r["client_name"], r["group_code"], r["project_code"],
             r["litigation"], r["litigation_intake_month"],
             r["days_in_litigation"], r["amount_involved"],
             SOURCE_TIER, METHOD),
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
    n_lit = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE litigation=1").fetchone()[0]
    rate = n_lit / got_total
    assert abs(rate - TRANSFER_RATE) < 0.002, f"litigation rate {rate}"
    print(f"check: litigation=1 rows {n_lit} (rate {rate:.4f}, target 0.04);")
    bad_id = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE "
        "(litigation=1 AND litigation_case_id IS NULL) OR "
        "(litigation=0 AND litigation_case_id IS NOT NULL)").fetchone()[0]
    assert bad_id == 0
    n_lit_id = con.execute(
        "SELECT COUNT(DISTINCT litigation_case_id) FROM cases_modelled "
        "WHERE litigation=1").fetchone()[0]
    assert n_lit_id == n_lit
    print("check: litigation_case_id present+unique exactly for litigation=1, "
          "in intake-month order;")
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
    print("check: section always 'Objections';")
    bad_amt = con.execute(
        "SELECT COUNT(*) FROM cases_modelled WHERE amount_involved IS NULL "
        "OR amount_involved < 1").fetchone()[0]
    assert bad_amt == 0
    medians = {}
    for cat, in con.execute("SELECT DISTINCT category FROM cases_modelled"):
        vals = sorted(r[0] for r in con.execute(
            "SELECT amount_involved FROM cases_modelled WHERE category=?", (cat,)))
        medians[cat] = vals[len(vals) // 2]
    parts = [c.split("_")[0] + "~" + format(m, ",d")
             for c, m in sorted(medians.items())]
    print("check: amount_involved all positive, no NULLs; category medians "
          "(CAD): " + ", ".join(parts) + ";")
    sample = con.execute(
        "SELECT objections_case_id, litigation_case_id, client_name, group_code, "
        "project_code FROM cases_modelled WHERE litigation=1 LIMIT 3").fetchall()
    print("sample litigation rows:", [tuple(s) for s in sample])
    print(f"check: transitions_modelled dropped (folded into cases).")
    con.commit()
    print(f"Wrote {DB} (cases_modelled {got_total} rows)")
    con.close()


if __name__ == "__main__":
    main()
