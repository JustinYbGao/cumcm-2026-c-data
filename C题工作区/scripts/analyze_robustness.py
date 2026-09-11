"""Paired stability analysis for the frozen robustness experiments."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / "results/robustness"
for _key in ("TMPDIR", "TMP", "TEMP"):
    os.environ[_key] = str(WORK / "data/interim/robustness")

import numpy as np
import pandas as pd

SEED = 20260910
REPLICATES = 5000
TIE_TOLERANCE_YUAN = 1e-6
PAIRS = [
    ("fixed_w14_vs_raw", "Fixed price: 14-day correction vs raw PV", "fixed_raw", "fixed_w14"),
    ("fixed_w28_vs_raw", "Fixed price: 28-day correction vs raw PV", "fixed_raw", "fixed_w28"),
    ("fixed_w56_vs_raw", "Fixed price: 56-day correction vs raw PV", "fixed_raw", "fixed_w56"),
    ("efficiency_w28_vs_raw", "Higher efficiency: 28-day correction vs raw PV", "efficiency_raw", "efficiency_w28"),
    ("soft_w28_vs_raw", "Soft terminal: 28-day correction vs raw PV", "soft_raw", "soft_w28"),
    ("variable_w28_vs_raw", "Variable price: 28-day correction vs raw PV", "variable_raw", "variable_w28"),
]
REQUIRED = ["date", "total_cost_yuan", "contract_cost_yuan", "emergency_cost_yuan",
            "emergency_kwh", "energy_start_actual_kwh", "energy_end_actual_kwh"]


@dataclass
class PairSummary:
    comparison_id: str
    comparison_label: str
    scope: str
    start_date: str
    end_date: str
    days: int
    raw_policy: str
    corrected_policy: str
    raw_total_cost_yuan: float
    corrected_total_cost_yuan: float
    cash_gain_yuan: float
    contract_cost_gain_yuan: float
    emergency_cost_gain_yuan: float
    emergency_energy_reduction_kwh: float
    raw_initial_energy_kwh: float
    raw_end_energy_kwh: float
    corrected_initial_energy_kwh: float
    corrected_end_energy_kwh: float
    inventory_value_yuan_per_kwh: float
    raw_inventory_adjusted_cost_yuan: float
    corrected_inventory_adjusted_cost_yuan: float
    inventory_adjusted_gain_yuan: float
    winning_days: int
    losing_days: int
    tie_days: int
    best_day: str
    best_daily_gain_yuan: float
    worst_day: str
    worst_daily_gain_yuan: float


def monthly_block_indices(dates, block_days, replicates, seed, method="moving_block"):
    """Sample contiguous blocks independently within each calendar month."""
    dates = pd.DatetimeIndex(dates)
    if method not in ("moving_block", "circular_block"):
        raise ValueError("unknown block method")
    if block_days <= 0 or replicates <= 0 or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("invalid bootstrap arguments")
    rng = np.random.default_rng(seed)
    result = np.empty((replicates, len(dates)), dtype=np.int32)
    periods = dates.to_period("M")
    month_positions = [np.flatnonzero(periods == month) for month in periods.unique()]
    if any(len(pos) < block_days for pos in month_positions):
        raise ValueError("block is longer than a month")
    for replicate in range(replicates):
        for positions in month_positions:
            sampled = []
            while len(sampled) < len(positions):
                if method == "moving_block":
                    start = int(rng.integers(0, len(positions) - block_days + 1))
                    block = positions[start:start + block_days]
                else:
                    start = int(rng.integers(0, len(positions)))
                    block = positions[(start + np.arange(block_days)) % len(positions)]
                sampled.extend(block.tolist())
            result[replicate, positions] = sampled[:len(positions)]
    return result


def analyze_pair(raw, corrected, comparison_id, comparison_label, inventory_value,
                 scope, raw_policy="raw", corrected_policy="corrected"):
    raw = raw.copy(); corrected = corrected.copy()
    raw["date"] = pd.to_datetime(raw.date); corrected["date"] = pd.to_datetime(corrected.date)
    if raw.date.tolist() != corrected.date.tolist() or raw.date.duplicated().any():
        raise ValueError("paired daily dates must be identical and unique")
    joined = raw[REQUIRED].merge(corrected[REQUIRED], on="date", suffixes=("_raw", "_corrected"), validate="one_to_one")
    joined.insert(0, "comparison_label", comparison_label)
    joined.insert(0, "comparison_id", comparison_id)
    joined["scope"] = scope
    joined["raw_policy"] = raw_policy; joined["corrected_policy"] = corrected_policy
    joined["cash_gain_yuan"] = joined.total_cost_yuan_raw - joined.total_cost_yuan_corrected
    joined["contract_cost_gain_yuan"] = joined.contract_cost_yuan_raw - joined.contract_cost_yuan_corrected
    joined["emergency_cost_gain_yuan"] = joined.emergency_cost_yuan_raw - joined.emergency_cost_yuan_corrected
    joined["emergency_energy_reduction_kwh"] = joined.emergency_kwh_raw - joined.emergency_kwh_corrected
    raw_change = joined.energy_end_actual_kwh_raw - joined.energy_start_actual_kwh_raw
    corrected_change = joined.energy_end_actual_kwh_corrected - joined.energy_start_actual_kwh_corrected
    joined["inventory_adjusted_daily_gain_yuan"] = joined.cash_gain_yuan - inventory_value * (raw_change - corrected_change)
    joined["cumulative_cash_gain_yuan"] = joined.cash_gain_yuan.cumsum()
    joined["cumulative_inventory_adjusted_gain_yuan"] = joined.inventory_adjusted_daily_gain_yuan.cumsum()
    joined["day_result"] = np.where(joined.cash_gain_yuan > TIE_TOLERANCE_YUAN, "corrected_lower_cost",
                            np.where(joined.cash_gain_yuan < -TIE_TOLERANCE_YUAN, "corrected_higher_cost", "tie"))
    joined["month"] = joined.date.dt.strftime("%Y-%m")
    monthly = joined.groupby("month", sort=True).agg(
        cash_gain_yuan=("cash_gain_yuan", "sum"),
        contract_cost_gain_yuan=("contract_cost_gain_yuan", "sum"),
        emergency_cost_gain_yuan=("emergency_cost_gain_yuan", "sum"),
        emergency_energy_reduction_kwh=("emergency_energy_reduction_kwh", "sum"),
        inventory_adjusted_gain_yuan=("inventory_adjusted_daily_gain_yuan", "sum"),
        raw_total_cost_yuan=("total_cost_yuan_raw", "sum"),
        corrected_total_cost_yuan=("total_cost_yuan_corrected", "sum"),
        raw_month_start_energy_kwh=("energy_start_actual_kwh_raw", "first"),
        raw_month_end_energy_kwh=("energy_end_actual_kwh_raw", "last"),
        corrected_month_start_energy_kwh=("energy_start_actual_kwh_corrected", "first"),
        corrected_month_end_energy_kwh=("energy_end_actual_kwh_corrected", "last"),
    ).reset_index()
    monthly.insert(0, "comparison_label", comparison_label); monthly.insert(0, "comparison_id", comparison_id)
    monthly["scope"] = scope
    monthly["cumulative_cash_gain_yuan"] = monthly.cash_gain_yuan.cumsum()
    raw_initial=float(joined.energy_start_actual_kwh_raw.iloc[0]); raw_end=float(joined.energy_end_actual_kwh_raw.iloc[-1])
    corrected_initial=float(joined.energy_start_actual_kwh_corrected.iloc[0]); corrected_end=float(joined.energy_end_actual_kwh_corrected.iloc[-1])
    raw_cost=float(joined.total_cost_yuan_raw.sum()); corrected_cost=float(joined.total_cost_yuan_corrected.sum())
    raw_adjusted=raw_cost-inventory_value*(raw_end-raw_initial)
    corrected_adjusted=corrected_cost-inventory_value*(corrected_end-corrected_initial)
    best=int(joined.cash_gain_yuan.to_numpy().argmax()); worst=int(joined.cash_gain_yuan.to_numpy().argmin())
    summary = PairSummary(
        comparison_id, comparison_label, scope, str(joined.date.iloc[0].date()), str(joined.date.iloc[-1].date()), len(joined),
        raw_policy, corrected_policy, raw_cost, corrected_cost, raw_cost-corrected_cost,
        float(joined.contract_cost_gain_yuan.sum()), float(joined.emergency_cost_gain_yuan.sum()),
        float(joined.emergency_energy_reduction_kwh.sum()), raw_initial, raw_end, corrected_initial, corrected_end,
        float(inventory_value), raw_adjusted, corrected_adjusted, raw_adjusted-corrected_adjusted,
        int((joined.day_result=="corrected_lower_cost").sum()), int((joined.day_result=="corrected_higher_cost").sum()),
        int((joined.day_result=="tie").sum()), str(joined.date.iloc[best].date()), float(joined.cash_gain_yuan.iloc[best]),
        str(joined.date.iloc[worst].date()), float(joined.cash_gain_yuan.iloc[worst]),
    )
    joined["date"] = joined.date.dt.strftime("%Y-%m-%d")
    return joined, monthly, summary


def bootstrap_intervals(daily):
    main = daily.loc[daily.scope == "april_december"].copy()
    dates = pd.DatetimeIndex(pd.to_datetime(main.loc[main.comparison_id == PAIRS[0][0], "date"]))
    methods = [("moving_block", 3), ("moving_block", 7), ("moving_block", 14), ("circular_block_control", 7)]
    rows = []
    for method, block in methods:
        sampler = "circular_block" if method.startswith("circular") else "moving_block"
        indices = monthly_block_indices(dates, block, REPLICATES, SEED, sampler)
        for comparison_id, label, _, _ in PAIRS:
            values = main.loc[main.comparison_id == comparison_id, "cash_gain_yuan"].to_numpy(float)
            estimates = values[indices].sum(axis=1)
            lower, upper = np.percentile(estimates, [2.5, 97.5])
            rows.append({"comparison_id": comparison_id, "comparison_label": label,
                "scope": "april_december", "estimand": "raw_minus_corrected_cash_cost_yuan",
                "method": method, "point_estimate_yuan": float(values.sum()),
                "lower_95_yuan": float(lower), "upper_95_yuan": float(upper),
                "positive_fraction": float(np.mean(estimates > 0)), "replicates": REPLICATES,
                "block_days": block, "seed": SEED})
    return pd.DataFrame(rows)


def main():
    missing = [str((OUT/p/"daily.csv").relative_to(WORK)) for _,_,raw,corrected in PAIRS for p in (raw,corrected)
               if not (OUT/p/"daily.csv").exists()]
    if missing:
        raise SystemExit("Robustness runner outputs are not ready: " + ", ".join(sorted(set(missing))))
    price = pd.read_csv(WORK/"data/processed/fixed_price.csv", float_precision="round_trip").price_yuan_per_kwh.to_numpy(float)
    inventory_value = float(price.mean() * 0.9)
    daily_outputs=[]; monthly_outputs=[]; summaries=[]
    for comparison_id,label,raw_policy,corrected_policy in PAIRS:
        raw=pd.read_csv(OUT/raw_policy/"daily.csv",float_precision="round_trip")
        corrected=pd.read_csv(OUT/corrected_policy/"daily.csv",float_precision="round_trip")
        if len(raw)!=334 or len(corrected)!=334 or str(raw.date.iloc[0])!="2025-02-01" or str(raw.date.iloc[-1])!="2025-12-31":
            raise ValueError(f"incomplete continuous daily inputs for {comparison_id}")
        full_daily,full_monthly,full_summary=analyze_pair(raw,corrected,comparison_id,label,inventory_value,
            "february_december",raw_policy,corrected_policy)
        main_raw=raw.loc[raw.date>="2025-04-01"].reset_index(drop=True)
        main_corrected=corrected.loc[corrected.date>="2025-04-01"].reset_index(drop=True)
        main_daily,main_monthly,main_summary=analyze_pair(main_raw,main_corrected,comparison_id,label,inventory_value,
            "april_december",raw_policy,corrected_policy)
        full_daily["is_main_evaluation"] = full_daily.date >= "2025-04-01"
        daily_outputs.extend([full_daily,main_daily]);monthly_outputs.extend([full_monthly,main_monthly])
        summaries.extend([asdict(full_summary),asdict(main_summary)])
    daily=pd.concat(daily_outputs,ignore_index=True);monthly=pd.concat(monthly_outputs,ignore_index=True)
    summary=pd.DataFrame(summaries);bootstrap=bootstrap_intervals(daily)
    # Keep one row per comparison/date in the daily export; its flag identifies the main interval.
    daily=daily.loc[daily.scope=="february_december"].drop(columns="scope")
    OUT.mkdir(parents=True,exist_ok=True)
    daily.to_csv(OUT/"paired_daily.csv",index=False);monthly.to_csv(OUT/"paired_monthly.csv",index=False)
    summary.to_csv(OUT/"paired_summary.csv",index=False);bootstrap.to_csv(OUT/"bootstrap_intervals.csv",index=False)
    checks={
        "six_comparisons": daily.comparison_id.nunique()==6,
        "complete_daily_pairs": len(daily)==6*334 and daily.groupby("comparison_id").size().eq(334).all(),
        "main_scope_275_days": summary.loc[summary.scope=="april_december","days"].eq(275).all(),
        "full_scope_334_days": summary.loc[summary.scope=="february_december","days"].eq(334).all(),
        "gain_breakdown": np.allclose(summary.cash_gain_yuan,summary.contract_cost_gain_yuan+summary.emergency_cost_gain_yuan,atol=1e-6,rtol=0),
        "daily_sign_counts": ((summary.winning_days+summary.losing_days+summary.tie_days)==summary.days).all(),
        "bootstrap_design": len(bootstrap)==24 and bootstrap.replicates.eq(REPLICATES).all() and bootstrap.seed.eq(SEED).all(),
        "finite_outputs": np.isfinite(summary.select_dtypes(include=[np.number])).all().all() and np.isfinite(bootstrap.select_dtypes(include=[np.number])).all().all(),
    }
    validation={"passed":bool(all(checks.values())),"checks":{k:bool(v) for k,v in checks.items()},
        "comparisons":6,"daily_rows":int(len(daily)),"monthly_rows":int(len(monthly)),"bootstrap_rows":int(len(bootstrap)),
        "inventory_value_yuan_per_kwh":inventory_value,"tie_tolerance_yuan":TIE_TOLERANCE_YUAN,
        "bootstrap":{"replicates":REPLICATES,"seed":SEED,"moving_block_days":[3,7,14],"circular_control_days":[7]},
        "interpretation":"Conditional retrospective resampling variability only; no future guarantee, fresh holdout, p-value, or distribution-free claim."}
    (OUT/"analysis_validation.json").write_text(json.dumps(validation,indent=2)+"\n")
    print(json.dumps(validation,indent=2))
    if not validation["passed"]:sys.exit(1)


if __name__=="__main__":main()
