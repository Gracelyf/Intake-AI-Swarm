"""Section B +20% intake scenario — capstone acceptance query 4 (Mon 2026-11-02).

Run from the repo folder (expects appeals.db alongside this script):

    python3 scenario_v1.py

WHAT THIS DOES:
  Retrospective stress test over fiscal 2024-25 (2024-04..2025-03):
    Inventory(t+1) = Inventory(t) + B_intake(t) x 1.2 - B_completions(t)
  plus Little's Law wait (W = inventory / monthly B completions) and the
  hold-flat FTE gap (extra cases x hours per case / effective hours),
  with a 3/4/5-hour sensitivity range.

WHERE THE INPUTS COME FROM (all already in appeals.db):
  - Litigation_intake(t)  = capacity_modelled Objections completions x TRANSFER_RATE
    (transfer happens at completion of the Objection stage — per Liang 2026-11-02;
    Litigation received ~= Objections processed x 0.04)
  - Litigation_completions(t) = Litigation_intake(t) x LITIGATION_COMPLETION_RATE
    (monthly completion rate is 80% of Litigation received — per Liang
    2026-11-02, domain knowledge)

THIS IS A LABELLED SCENARIO, NOT A FORECAST. Key assumptions (all labelled
in the output):
  1. objections processed = Objections completions (confirmed 2026-11-02).
  2. Litigation intake ~= Objections processed x 0.04 (transfer at completion).
  3. Litigation completions = 80% of Litigation received each month (Liang's
     domain knowledge). Note this means the Litigation backlog grows even at
     baseline (completions < intake) — the scenario shows how much faster.
  4. Opening Litigation inventory ~= total 2023-24 net x 0.04 (proportionality
     assumption). 2022-23 net is unknown (processed NULL), so the level is
     approximate; the *change* over the 12 months is the robust part.
  5. hours_per_case (4h) and effective_hours_per_fte_month (140h) are pure
     assumptions, pending confirmation.
"""

from pathlib import Path
import sqlite3

BASE = Path(__file__).parent
DB = BASE / "appeals.db"

# --- v1 parameters (assumptions — change and re-run) ---
TRANSFER_RATE = 0.04          # Objections -> Litigation transfer rate (locked 2026-10-30)
LITIGATION_COMPLETION_RATE = 0.80  # monthly Litigation completions = 80% of Litigation received (Liang domain knowledge, 2026-11-02)
SCENARIO_UPLIFT = 1.2         # +20% Litigation intake
FY = "2024-25"                # retrospective window
HOURS_PER_CASE_RANGE = (3.0, 4.0, 5.0)   # sensitivity range
EFFECTIVE_HOURS_PER_FTE_MONTH = 140.0
OPENING_TOTAL_NET_2324 = 87543 - 82764   # = 4779, verified annual_real


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    months = [r["calendar_month"] for r in con.execute(
        "SELECT calendar_month FROM capacity_modelled "
        "WHERE fiscal_year=? AND series='objections' AND section='Objections' "
        "ORDER BY calendar_month",
        (FY,))]
    assert len(months) == 12, f"expected 12 months for {FY}"

    comp_a = {r["calendar_month"]: r["completions_modelled"] for r in con.execute(
        "SELECT calendar_month, completions_modelled FROM capacity_modelled "
        "WHERE fiscal_year=? AND series='objections' AND section='Objections'", (FY,))}
    assert len(comp_a) == 12, "capacity_modelled Objections rows missing"

    opening_b = OPENING_TOTAL_NET_2324 * TRANSFER_RATE
    print(f"SCENARIO (not a forecast): Litigation intake x{SCENARIO_UPLIFT} "
          f"over {FY} (12 months)")
    print(f"Assumptions: transfer rate={TRANSFER_RATE}; "
          f"Litigation intake ~= Objections processed x {TRANSFER_RATE} "
          f"(transfer at completion, per Liang 2026-11-02); "
          f"Litigation completions = {LITIGATION_COMPLETION_RATE:.0%} of Litigation "
          f"received each month (Liang domain knowledge); "
          f"opening Litigation inventory ~= 2023-24 net "
          f"{OPENING_TOTAL_NET_2324} x {TRANSFER_RATE} = {opening_b:.1f}; "
          f"hours/case {HOURS_PER_CASE_RANGE}, {EFFECTIVE_HOURS_PER_FTE_MONTH}h/FTE-month "
          f"(both pure assumptions).")
    print(f"{'month':<8}{'Lit intake':>10}{'x1.2':>9}{'Lit compl':>10}{'invent':>9}{'wait(mo)':>9}")

    inv = opening_b
    peak_inv, peak_m = inv, months[0]
    total_extra_cases = 0.0
    peak_extra_cases, peak_extra_m = 0.0, months[0]
    for m in months:
        b_in = comp_a[m] * TRANSFER_RATE
        b_in_scen = b_in * SCENARIO_UPLIFT
        b_comp = b_in * LITIGATION_COMPLETION_RATE
        extra = b_in_scen - b_in
        total_extra_cases += extra
        if extra > peak_extra_cases:
            peak_extra_cases, peak_extra_m = extra, m
        inv = inv + b_in_scen - b_comp
        assert inv >= 0, f"negative inventory in {m} — check assumptions"
        if inv > peak_inv:
            peak_inv, peak_m = inv, m
        wait = inv / b_comp
        print(f"{m:<8}{b_in:>9.1f}{b_in_scen:>9.1f}{b_comp:>9.1f}"
              f"{inv:>9.1f}{wait:>9.2f}")

    end_wait = inv / (comp_a[months[-1]] * TRANSFER_RATE * LITIGATION_COMPLETION_RATE)
    print(f"\nEnd inventory: {inv:.0f} cases (opened at {opening_b:.0f}); "
          f"peak {peak_inv:.0f} in {peak_m}.")
    print(f"Implied wait (Little's Law): {opening_b / (comp_a[months[0]] * TRANSFER_RATE):.1f} "
          f"-> {end_wait:.1f} months.")
    print(f"Total extra Litigation cases over 12 months: {total_extra_cases:.0f}.")
    print("Hold-flat FTE gap (extra cases x hours/case / 140h):")
    for h in HOURS_PER_CASE_RANGE:
        fte_months = total_extra_cases * h / EFFECTIVE_HOURS_PER_FTE_MONTH
        print(f"  {h:.0f}h/case: {fte_months:.1f} FTE-months "
              f"(~= {fte_months / 12:.1f} ongoing FTE)")
    peak_fte = peak_extra_cases * HOURS_PER_CASE_RANGE[1] / EFFECTIVE_HOURS_PER_FTE_MONTH
    print(f"Peak month ({peak_extra_m}): +{peak_extra_cases:.0f} cases -> "
          f"+{peak_fte:.1f} FTE that month at 4h/case.")
    print("Limits: Litigation-inventory LEVEL is approximate (2022-23 net unknown; "
          "proportionality assumptions); the 12-month CHANGE is the robust output.")
    con.close()


if __name__ == "__main__":
    main()
