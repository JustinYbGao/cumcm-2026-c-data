"""Prepare traceable compact inputs for three explanatory v5 paper figures.

The script reads verified outputs only.  It never rewrites source ledgers,
workbooks, or cleaned input tables.  Every transformed plotting table and the
hashes of its direct sources remain in the versioned figure package.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PROJECT = Path(__file__).resolve().parents[2]
RESULTS = PROJECT / "results" / "unified_direct_v5"
ROOT = PROJECT / "reports" / "figures" / "paper_visuals_v4_explanation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_q3_monthly_saving() -> dict[str, object]:
    source = RESULTS / "paired_monthly.csv"
    paired = pd.read_csv(source)
    soc = paired.loc[
        (paired["candidate"] == "q3_soc") & (paired["reference"] == "q3_no_update"),
        ["month", "saving_yuan"],
    ].rename(columns={"saving_yuan": "soc_saving_yuan"})
    raw_increment = paired.loc[
        (paired["candidate"] == "q3_raw") & (paired["reference"] == "q3_soc"),
        ["month", "saving_yuan"],
    ].rename(columns={"saving_yuan": "raw_increment_saving_yuan"})
    output = soc.merge(raw_increment, on="month", validate="one_to_one").sort_values("month")
    output["raw_vs_no_update_saving_yuan"] = (
        output["soc_saving_yuan"] + output["raw_increment_saving_yuan"]
    )
    output["cumulative_raw_vs_no_update_saving_yuan"] = output[
        "raw_vs_no_update_saving_yuan"
    ].cumsum()
    destination = ROOT / "q3_monthly_saving" / "data" / "q3_monthly_saving.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False)
    return {
        "source": str(source.resolve()),
        "sha256": sha256(source),
        "transformation": (
            "For each month, raw-PV saving versus no-update equals the recorded "
            "SOC-feedback saving versus no-update plus the recorded raw-PV "
            "incremental saving versus SOC feedback."
        ),
    }


def prepare_q3_peak_day() -> dict[str, object]:
    source = RESULTS / "runs" / "q3_raw" / "ledger.csv"
    ledger = pd.read_csv(source)
    daily_emergency = ledger.groupby("date", sort=True)["emergency_kwh"].sum()
    peak_date = str(daily_emergency.idxmax())
    day = ledger.loc[ledger["date"] == peak_date].copy().sort_values("slot_id")
    day["hour"] = (day["slot_id"] - 1) / 6
    day["net_load_kwh"] = day["load_actual_kwh"] - day["pv_actual_kwh"]
    day["battery_net_kwh"] = day["discharge_actual_kwh"] - day["charge_actual_kwh"]
    output = day[
        [
            "slot_id",
            "hour",
            "net_load_kwh",
            "grid_effective_kwh",
            "emergency_kwh",
            "battery_net_kwh",
            "energy_end_actual_kwh",
        ]
    ]
    destination = ROOT / "q3_peak_day_execution" / "data" / "q3_peak_day_execution.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False)
    return {
        "source": str(source.resolve()),
        "sha256": sha256(source),
        "selection_rule": "Choose the date with the largest total realized emergency purchase in q3_raw.",
        "selected_date": peak_date,
        "selected_date_emergency_kwh": float(daily_emergency.loc[peak_date]),
    }


def prepare_q43_causal_trace() -> dict[str, object]:
    plans_source = RESULTS / "runs" / "q43_raw_ols" / "plan_versions.csv"
    ledger_source = RESULTS / "runs" / "q43_raw_ols" / "ledger.csv"
    plans = pd.read_csv(plans_source)
    ledger = pd.read_csv(ledger_source)
    audit_date = "2025-07-14"  # A published causal-audit day in the v5 package.
    plan_day = plans.loc[plans["date"] == audit_date].copy()
    ledger_day = ledger.loc[ledger["date"] == audit_date].copy()
    if plan_day.empty or ledger_day.empty:
        raise ValueError(f"The declared causal-audit date {audit_date} is unavailable.")
    output = ledger_day[
        ["slot_id", "price_yuan_per_kwh", "grid_effective_kwh"]
    ].rename(
        columns={
            "price_yuan_per_kwh": "actual_price_yuan_per_kwh",
            "grid_effective_kwh": "executed_grid_kwh",
        }
    )
    for issue_hour in (0, 6, 12, 18):
        version = plan_day.loc[plan_day["issue_hour"] == issue_hour, [
            "slot_id",
            "price_forecast_yuan_per_kwh",
            "grid_kwh",
        ]].rename(
            columns={
                "price_forecast_yuan_per_kwh": f"price_forecast_{issue_hour}_yuan_per_kwh",
                "grid_kwh": f"grid_plan_{issue_hour}_kwh",
            }
        )
        output = output.merge(version, on="slot_id", how="left", validate="one_to_one")
    output["hour"] = (output["slot_id"] - 1) / 6
    output = output.sort_values("slot_id")
    destination = ROOT / "q43_causal_trace" / "data" / "q43_causal_trace.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False)
    return {
        "sources": {
            str(plans_source.resolve()): sha256(plans_source),
            str(ledger_source.resolve()): sha256(ledger_source),
        },
        "selection_rule": "Use the predeclared causal-audit date 2025-07-14; no outcome-based date selection is used.",
        "selected_date": audit_date,
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    provenance = {
        "source_root": str(RESULTS.resolve()),
        "q3_monthly_saving": prepare_q3_monthly_saving(),
        "q3_peak_day_execution": prepare_q3_peak_day(),
        "q43_causal_trace": prepare_q43_causal_trace(),
        "units": {
            "energy": "kWh per 10-minute interval",
            "state_of_charge": "kWh",
            "price": "CNY/kWh",
            "saving": "CNY",
        },
    }
    (ROOT / "source_hashes.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
