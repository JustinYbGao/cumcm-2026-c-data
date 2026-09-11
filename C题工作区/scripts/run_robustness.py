"""Run the frozen ten-policy assumption and PV-correction robustness replay."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from innovation_core import solve
from run_q3 import contract_fee, execute_interval, export_policy, select_forecast


sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
OUT = WORK / "results" / "robustness"
TEMP = WORK / "data" / "interim" / "robustness"
for _key in ("TMPDIR", "TMP", "TEMP"):
    os.environ[_key] = str(TEMP)


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, float_precision="round_trip", **kwargs)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correction_active(policy: dict, issue, config: dict) -> bool:
    return policy["pv_window_days"] is not None and pd.Timestamp(issue) >= pd.Timestamp(config["correction_start"])


def correct_pv(history: pd.DataFrame, issue, window_days: int, raw) -> tuple[np.ndarray, dict]:
    """Fit a causal additive daylight bias and apply it only to positive raw PV."""
    issue = pd.Timestamp(issue)
    cutoff = issue.normalize()
    start = cutoff - pd.Timedelta(days=int(window_days))
    values = np.asarray(raw, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("raw PV must be a finite nonnegative vector")
    frame = history.copy()
    for column in ("issue_time", "interval_start", "interval_end"):
        frame[column] = pd.to_datetime(frame[column])
    eligible = frame.loc[
        (frame.issue_time < issue)
        & (frame.issue_time.dt.hour == issue.hour)
        & (frame.interval_start >= start)
        & (frame.interval_end <= cutoff)
        & (frame.pv_forecast_kwh > 0)
    ].copy()
    bias = float(eligible.residual_kwh.mean()) if len(eligible) else 0.0
    positive = values > 0
    corrected = np.where(positive, np.maximum(0.0, values + bias), 0.0)
    meta = {
        "active": True,
        "issue_time": str(issue),
        "issue_hour": int(issue.hour),
        "window_days": int(window_days),
        "window_start": str(start),
        "training_cutoff": str(cutoff),
        "training_rows": int(len(eligible)),
        "positive_training_rows": int(len(eligible)),
        "latest_target_end": None if eligible.empty else str(pd.Timestamp(eligible.interval_end.max())),
        "bias_kwh": bias,
        "active_positive_intervals": int(positive.sum()),
        "clipped_intervals": int((positive & (values + bias < 0)).sum()),
    }
    return corrected, meta


def inactive_correction(issue, raw, window_days) -> tuple[np.ndarray, dict]:
    values = np.asarray(raw, dtype=float).copy()
    issue = pd.Timestamp(issue)
    return values, {
        "active": False,
        "issue_time": str(issue),
        "issue_hour": int(issue.hour),
        "window_days": window_days,
        "window_start": None,
        "training_cutoff": str(issue.normalize()),
        "training_rows": 0,
        "positive_training_rows": 0,
        "latest_target_end": None,
        "bias_kwh": 0.0,
        "active_positive_intervals": int((values > 0).sum()),
        "clipped_intervals": 0,
    }


def bill(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    price = result.settlement_price_yuan_per_kwh.to_numpy(float)
    original = result.grid_original_kwh.to_numpy(float)
    effective = result.grid_effective_kwh.to_numpy(float)
    delta = effective - original
    result["price_yuan_per_kwh"] = price
    result["original_cost_yuan"] = price * original
    result["increase_cost_yuan"] = 1.5 * price * np.maximum(delta, 0)
    result["decrease_adjustment_yuan"] = -0.5 * price * np.maximum(-delta, 0)
    result["contract_cost_yuan"] = (
        result.original_cost_yuan + result.increase_cost_yuan + result.decrease_adjustment_yuan
    )
    result["emergency_cost_yuan"] = 5 * price * result.emergency_kwh
    result["total_cost_yuan"] = result.contract_cost_yuan + result.emergency_cost_yuan
    return result


class Inputs:
    """Robustness-scoped input cache; construction writes no legacy output."""

    def __init__(self, config: dict):
        self.config = config
        self.physical = json.loads((WORK / "configs/model_baseline.json").read_text())
        self.fixed_price = read_csv(WORK / "data/processed/fixed_price.csv").price_yuan_per_kwh.to_numpy(float)
        self.inventory_reference = float(0.9 * self.fixed_price.mean())
        actual = read_csv(WORK / "data/processed/actual_10min.csv")
        for column in ("interval_start", "interval_end"):
            actual[column] = pd.to_datetime(actual[column])
        self.actual_days = {date: frame.reset_index(drop=True) for date, frame in actual.groupby("date", sort=False)}
        truth = actual[["interval_start", "pv_actual_kwh"]]

        q2 = read_csv(WORK / "results/q2/selected/ledger.csv", usecols=["date", "load_forecast_kwh"])
        self.load_days = {date: frame.load_forecast_kwh.to_numpy(float) for date, frame in q2.groupby("date", sort=False)}

        pv = read_csv(WORK / "data/processed/pv_forecast_10min.csv")
        for column in ("issue_time", "interval_start", "interval_end"):
            pv[column] = pd.to_datetime(pv[column])
        self.pv_issues = {issue: frame for issue, frame in pv.groupby("issue_time", sort=False)}
        same_day = pv.loc[
            (pv.interval_end <= pv.issue_time.dt.normalize() + pd.Timedelta(days=1))
            & (pv.pv_forecast_kwh > 0)
        ].merge(truth, on="interval_start", how="inner", validate="many_to_one")
        same_day["residual_kwh"] = same_day.pv_actual_kwh - same_day.pv_forecast_kwh
        self.pv_history = same_day

        prices = read_csv(WORK / "results/q4/price_forecasts.csv")
        for column in ("issue_time", "interval_start", "interval_end"):
            prices[column] = pd.to_datetime(prices[column])
        self.price_issues = {issue: frame for issue, frame in prices.groupby("issue_time", sort=False)}
        self.initial_energy = float(config["initial_energy_kwh"])

    def pv_forecast(self, issue, end) -> pd.DataFrame:
        issue = pd.Timestamp(issue)
        return select_forecast(self.pv_issues[issue], issue, end)

    def q4_prices(self, issue, end) -> np.ndarray:
        issue, end = pd.Timestamp(issue), pd.Timestamp(end)
        frame = self.price_issues[issue]
        frame = frame.loc[(frame.interval_start >= issue) & (frame.interval_end <= end)].sort_values("interval_start")
        wanted = pd.date_range(issue, end, freq="10min", inclusive="left")
        if len(frame) != len(wanted) or not np.array_equal(frame.interval_start.to_numpy(), wanted.to_numpy()):
            raise ValueError("Q4 price forecast coverage mismatch")
        values = frame.price_forecast_yuan_per_kwh.to_numpy(float)
        if not np.all(np.isfinite(values)) or np.any(values <= 0):
            raise ValueError("Q4 planning prices must be finite and positive")
        return values


def policy_physical(data: Inputs, settings: dict) -> dict:
    physical = copy.deepcopy(data.physical)
    physical["battery"]["eta_charge"] = float(settings["eta_charge"])
    physical["battery"]["eta_discharge"] = float(settings["eta_discharge"])
    return physical


def run_policy(data: Inputs, policy: str, settings: dict, bias_records: list[dict]) -> dict:
    folder = OUT / policy
    if (folder / "summary.json").exists():
        raise FileExistsError(f"Preserve existing completed policy output: {folder}")
    physical = policy_physical(data, settings)
    eta_c = float(settings["eta_charge"])
    eta_d = float(settings["eta_discharge"])
    soft = settings["terminal"] == "soft"
    terminal_penalty = data.inventory_reference if soft else None
    energy = data.initial_energy
    ledgers, versions, statuses = [], [], []

    for day in pd.date_range(data.config["evaluation_start"], data.config["evaluation_end"]):
        date = str(day.date())
        end = day + pd.Timedelta(days=1)
        actual = data.actual_days[date]
        load = data.load_days[date]
        actual_prices = actual.actual_price_yuan_per_kwh.to_numpy(float)
        settlement_prices = data.fixed_price if settings["settlement_price"] == "fixed" else actual_prices
        day_initial = energy
        original = None
        current = np.zeros(144)
        events = []

        for slot in range(144):
            if slot in {hour * 6 for hour in data.config["update_hours"]}:
                issue = day + pd.Timedelta(minutes=10 * slot)
                forecast = data.pv_forecast(issue, end)
                raw_pv = forecast.pv_forecast_kwh.to_numpy(float)
                if correction_active(settings, issue, data.config):
                    used_pv, correction = correct_pv(
                        data.pv_history, issue, int(settings["pv_window_days"]), raw_pv
                    )
                    bias_records.append({"policy": policy, **correction})
                    pv_method = f"bias_w{settings['pv_window_days']}"
                else:
                    used_pv, correction = inactive_correction(issue, raw_pv, settings["pv_window_days"])
                    pv_method = "raw"
                if settings["planning_price"] == "fixed":
                    planning_prices = data.fixed_price[slot:]
                    planning_price_source = "data/processed/fixed_price.csv"
                else:
                    planning_prices = data.q4_prices(issue, end)
                    planning_price_source = "results/q4/price_forecasts.csv"
                kwargs = {"soft_terminal": soft}
                if soft:
                    kwargs["terminal_penalty"] = terminal_penalty
                plan, status = solve(
                    load[slot:], used_pv, planning_prices, energy, day_initial, physical,
                    original=None if original is None else original[slot:], **kwargs,
                )
                if original is None:
                    original = np.maximum(0.0, plan["grid_kwh"].copy())
                current[slot:] = np.maximum(0.0, plan["grid_kwh"])
                version = pd.DataFrame(
                    {
                        "policy": policy,
                        "date": date,
                        "issue_hour": slot // 6,
                        "issue_time": str(issue),
                        "slot_id": np.arange(slot + 1, 145),
                        "interval_start": forecast.interval_start.to_numpy(),
                        "interval_end": forecast.interval_end.to_numpy(),
                        "load_forecast_kwh": load[slot:],
                        "pv_method": pv_method,
                        "pv_window_days": settings["pv_window_days"],
                        "pv_raw_forecast_kwh": raw_pv,
                        "pv_corrected_forecast_kwh": used_pv,
                        "pv_forecast_kwh": used_pv,
                        "endpoint_rule": forecast.endpoint_rule.to_numpy(),
                        "endpoint_issue_time": forecast.endpoint_issue_time.to_numpy(),
                        "planning_price_method": settings["planning_price"],
                        "planning_price_source": planning_price_source,
                        "planning_price_yuan_per_kwh": planning_prices,
                        "eta_charge": eta_c,
                        "eta_discharge": eta_d,
                        "soft_terminal": soft,
                        "terminal_penalty_yuan_per_kwh": terminal_penalty,
                        "grid_original_kwh": original[slot:],
                    }
                )
                for key, values in plan.items():
                    version[key] = values
                version["contract_cost_forecast_yuan"] = contract_fee(
                    original[slot:], plan["grid_kwh"], planning_prices, "A"
                )
                versions.append(version)
                statuses.append(
                    {
                        "policy": policy,
                        "date": date,
                        "issue_hour": slot // 6,
                        "issue_time": str(issue),
                        "horizon_intervals": 144 - slot,
                        "initial_energy_kwh": float(energy),
                        "terminal_target_kwh": float(day_initial),
                        "load_issue_time": str(day),
                        "eta_charge": eta_c,
                        "eta_discharge": eta_d,
                        "soft_terminal": soft,
                        "terminal_penalty_yuan_per_kwh": terminal_penalty,
                        "pv_method": pv_method,
                        "pv_window_days": settings["pv_window_days"],
                        "correction": correction,
                        "planning_price_method": settings["planning_price"],
                        "planning_price_source": planning_price_source,
                        "settlement_price_method": settings["settlement_price"],
                        "settlement_price_source": (
                            "data/processed/fixed_price.csv" if settings["settlement_price"] == "fixed"
                            else "data/processed/actual_10min.csv#actual_price_yuan_per_kwh"
                        ),
                        "solver": status,
                    }
                )
                active_slot = slot
                active_issue = issue
                active_raw = raw_pv
                active_used = used_pv
                active_planning_prices = planning_prices
                active_pv_method = pv_method

            index = slot - active_slot
            row = actual.iloc[slot]
            quantity = max(0.0, float(current[slot]))
            event = execute_interval(
                quantity, float(row.load_actual_kwh), float(row.pv_actual_kwh), energy, eta_c, eta_d
            )
            energy = event["energy_end_actual_kwh"]
            event.update(
                policy=policy,
                date=date,
                slot_id=slot + 1,
                interval_start=str(row.interval_start),
                interval_end=str(row.interval_end),
                active_issue_hour=active_slot // 6,
                active_issue_time=str(active_issue),
                load_actual_kwh=float(row.load_actual_kwh),
                pv_actual_kwh=float(row.pv_actual_kwh),
                load_forecast_kwh=float(load[slot]),
                pv_method=active_pv_method,
                pv_window_days=settings["pv_window_days"],
                pv_raw_forecast_kwh=float(active_raw[index]),
                pv_corrected_forecast_kwh=float(active_used[index]),
                pv_forecast_kwh=float(active_used[index]),
                planning_price_method=settings["planning_price"],
                planning_price_source=planning_price_source,
                planning_price_yuan_per_kwh=float(active_planning_prices[index]),
                actual_price_yuan_per_kwh=float(actual_prices[slot]),
                settlement_price_yuan_per_kwh=float(settlement_prices[slot]),
                grid_original_kwh=float(original[slot]),
                grid_effective_kwh=quantity,
            )
            events.append(event)

        ledgers.append(bill(pd.DataFrame(events)))
        if day.day == 1:
            print(policy, date, "SOC", round(energy, 6), flush=True)

    ledger = pd.concat(ledgers, ignore_index=True)
    total = export_policy(folder, ledger, pd.concat(versions, ignore_index=True), statuses, "A")
    april = ledger.loc[ledger.date >= data.config["correction_start"]]
    april_start = float(april.energy_start_actual_kwh.iloc[0])
    april_end = float(april.energy_end_actual_kwh.iloc[-1])
    total.update(
        policy=policy,
        planning_price=settings["planning_price"],
        settlement_price=settings["settlement_price"],
        eta_charge=eta_c,
        eta_discharge=eta_d,
        terminal=settings["terminal"],
        pv_window_days=settings["pv_window_days"],
        inventory_reference_yuan_per_kwh=data.inventory_reference,
        inventory_adjustment_yuan=float(-data.inventory_reference * (energy - data.initial_energy)),
        inventory_adjusted_cost_yuan=float(total["total_cost_yuan"] - data.inventory_reference * (energy - data.initial_energy)),
        april_december_cost_yuan=float(april.total_cost_yuan.sum()),
        april_december_initial_energy_kwh=april_start,
        april_december_final_energy_kwh=april_end,
        april_december_inventory_adjustment_yuan=float(-data.inventory_reference * (april_end - april_start)),
        april_december_inventory_adjusted_cost_yuan=float(
            april.total_cost_yuan.sum() - data.inventory_reference * (april_end - april_start)
        ),
    )
    write_json(folder / "summary.json", total)
    print(policy, "cost", format(total["total_cost_yuan"], ".6f"), flush=True)
    return total


def source_paths() -> list[str]:
    return [
        "configs/robustness.json", "configs/model_baseline.json", "configs/q4_baseline.json",
        "scripts/run_robustness.py", "scripts/innovation_core.py", "scripts/run_q3.py",
        "scripts/run_q4.py", "scripts/run_q2.py", "scripts/solve_q1.py",
        "tests/test_robustness.py",
        "data/processed/actual_10min.csv", "data/processed/fixed_price.csv",
        "data/processed/pv_forecast_10min.csv", "results/q2/selected/ledger.csv",
        "results/q2/selection.json", "results/q4/price_forecasts.csv",
        "results/q4/price_models.json", "results/q4/run_status.json",
        "reports/robustness/execution_plan.md",
    ]


def source_hashes() -> dict[str, str]:
    return {name: sha256(WORK / name) for name in source_paths()}


def pair_comparisons(comparison: pd.DataFrame) -> pd.DataFrame:
    by_policy = comparison.set_index("policy")
    pairs = [
        ("fixed_w14", "fixed_raw", "fixed", 14),
        ("fixed_w28", "fixed_raw", "fixed", 28),
        ("fixed_w56", "fixed_raw", "fixed", 56),
        ("efficiency_w28", "efficiency_raw", "efficiency", 28),
        ("soft_w28", "soft_raw", "soft_terminal", 28),
        ("variable_w28", "variable_raw", "variable_price", 28),
    ]
    rows = []
    for corrected, raw, setting, window in pairs:
        c, r = by_policy.loc[corrected], by_policy.loc[raw]
        rows.append(
            {
                "setting": setting,
                "window_days": window,
                "raw_policy": raw,
                "corrected_policy": corrected,
                "april_december_raw_cost_yuan": float(r.april_december_cost_yuan),
                "april_december_corrected_cost_yuan": float(c.april_december_cost_yuan),
                "april_december_saving_yuan": float(r.april_december_cost_yuan - c.april_december_cost_yuan),
                "april_december_raw_inventory_adjusted_cost_yuan": float(r.april_december_inventory_adjusted_cost_yuan),
                "april_december_corrected_inventory_adjusted_cost_yuan": float(c.april_december_inventory_adjusted_cost_yuan),
                "april_december_inventory_adjusted_saving_yuan": float(
                    r.april_december_inventory_adjusted_cost_yuan - c.april_december_inventory_adjusted_cost_yuan
                ),
                "full_334_raw_cost_yuan": float(r.total_cost_yuan),
                "full_334_corrected_cost_yuan": float(c.total_cost_yuan),
                "full_334_saving_yuan": float(r.total_cost_yuan - c.total_cost_yuan),
                "is_final_deployed_w28_comparison": setting == "fixed" and window == 28,
            }
        )
    return pd.DataFrame(rows)


def run() -> None:
    config = json.loads((WORK / "configs/robustness.json").read_text())
    existing_status = OUT / "run_status.json"
    if existing_status.exists() and json.loads(existing_status.read_text()).get("completed"):
        raise FileExistsError("Preserve completed robustness output; use a new version")
    TEMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    write_json(OUT / "input_code_hashes_before.json", before)
    write_json(OUT / "config_snapshot.json", config)
    write_json(
        existing_status,
        {"completed": False, "state": "running", "policies": list(config["policies"]), "formal_excel_exported": False},
    )
    data = Inputs(config)
    if abs(data.initial_energy - float(config["initial_energy_kwh"])) > 1e-12:
        raise ValueError("unexpected initial energy")
    results, bias_records = [], []
    for policy, settings in config["policies"].items():
        results.append(run_policy(data, policy, settings, bias_records))
    comparison = pd.DataFrame(results)
    comparison.to_csv(OUT / "comparison.csv", index=False)
    pair_comparisons(comparison).to_csv(OUT / "paired_comparison.csv", index=False)
    write_json(OUT / "pv_bias_models.json", bias_records)

    after = source_hashes()
    write_json(OUT / "input_code_hashes_after.json", after)
    if before != after:
        raise RuntimeError("input, code or config changed during execution")
    observed = float(comparison.loc[comparison.policy == "fixed_raw", "total_cost_yuan"].iloc[0])
    expected = float(config["expected_fixed_raw_total_cost_yuan"])
    difference = observed - expected
    if abs(difference) > float(config["baseline_tolerance_yuan"]):
        raise AssertionError(f"fixed_raw baseline mismatch: {observed} versus {expected}")
    status = {
        "completed": True,
        "state": "completed",
        "inputs_unchanged": True,
        "policies": list(config["policies"]),
        "policy_count": len(config["policies"]),
        "evaluation_days_each": 334,
        "evaluation_intervals_each": 48096,
        "continuous_state_across_days": True,
        "fixed_raw_expected_total_cost_yuan": expected,
        "fixed_raw_observed_total_cost_yuan": observed,
        "fixed_raw_difference_yuan": difference,
        "baseline_matches": True,
        "input_code_hashes_before_sha256": sha256(OUT / "input_code_hashes_before.json"),
        "input_code_hashes_after_sha256": sha256(OUT / "input_code_hashes_after.json"),
        "config_sha256": sha256(WORK / "configs/robustness.json"),
        "formal_excel_exported": False,
        "retrospective": True,
    }
    write_json(existing_status, status)
    print(comparison[["policy", "total_cost_yuan", "april_december_cost_yuan", "final_energy_kwh"]].to_string(index=False), flush=True)


def main() -> None:
    try:
        run()
    except Exception as error:
        OUT.mkdir(parents=True, exist_ok=True)
        status_path = OUT / "run_status.json"
        if not (status_path.exists() and json.loads(status_path.read_text()).get("completed")):
            write_json(status_path, {"completed": False, "state": "failed", "error": f"{type(error).__name__}: {error}"})
        raise


if __name__ == "__main__":
    main()
