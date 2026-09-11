"""Prepare small, traceable plotting tables from the verified v5 result bundle.

The script never changes source data.  It creates only the compact tables used by
the two revised paper figures and records SHA-256 hashes of the source files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PROJECT = Path(__file__).resolve().parents[2]
V5_RESULTS = PROJECT / "results" / "unified_direct_v5"
OUT = PROJECT / "reports" / "figures" / "paper_visuals_v3_v5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_table(frame: pd.DataFrame, relative_path: str) -> None:
    path = OUT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")


def main() -> None:
    comparison_path = V5_RESULTS / "comparison_all.csv"
    monthly_path = V5_RESULTS / "paired_monthly.csv"
    summary_path = V5_RESULTS / "paired_summary.csv"
    comparison = pd.read_csv(comparison_path)
    paired_monthly = pd.read_csv(monthly_path)

    q3_ids = ["q3_no_update", "q3_soc", "q3_raw", "q3_w28"]
    q3 = comparison.loc[comparison["policy"].isin(q3_ids)].copy()
    order = {policy_id: index for index, policy_id in enumerate(q3_ids)}
    labels = {
        "q3_no_update": "No update",
        "q3_soc": "SOC feedback",
        "q3_raw": "Raw PV update\n(selected)",
        "q3_w28": "28-day correction\n(not selected)",
    }
    q3["policy_order"] = q3["policy"].map(order)
    q3["policy_label"] = q3["policy"].map(labels)
    q3["contract_cost_million_cny"] = q3["contract_cost_yuan"] / 1_000_000
    q3["emergency_cost_million_cny"] = q3["emergency_cost_yuan"] / 1_000_000
    q3["total_cost_million_cny"] = q3["total_cost_yuan"] / 1_000_000
    q3["selected"] = q3["policy"].eq("q3_raw")
    q3 = q3.sort_values("policy_order")
    save_table(
        q3[
            [
                "policy",
                "policy_label",
                "policy_order",
                "contract_cost_million_cny",
                "emergency_cost_million_cny",
                "total_cost_million_cny",
                "selected",
            ]
        ],
        "q3_policy_costs/data/q3_policy_costs.csv",
    )

    q4_pairs = {
        "q42_ols_vs_fixed": {
            "candidate": "q42_ols",
            "reference": "q42_fixed",
            "label": "Q4-2: OLS − fixed",
        },
        "q43_ols_vs_fixed": {
            "candidate": "q43_raw_ols",
            "reference": "q43_raw_fixed",
            "label": "Q4-3: OLS − fixed",
        },
    }
    q4_frames = []
    for pair_id, info in q4_pairs.items():
        rows = paired_monthly.loc[
            (paired_monthly["candidate"] == info["candidate"])
            & (paired_monthly["reference"] == info["reference"])
        ].copy()
        if rows.empty:
            raise ValueError(f"No monthly paired results for {pair_id}.")
        rows["comparison_id"] = pair_id
        rows["comparison_label"] = info["label"]
        rows["monthly_saving_yuan"] = rows["saving_yuan"]
        rows["cumulative_saving_yuan"] = rows["saving_yuan"].cumsum()
        q4_frames.append(rows)
    q4 = pd.concat(q4_frames, ignore_index=True)
    save_table(
        q4[
            [
                "comparison_id",
                "comparison_label",
                "month",
                "monthly_saving_yuan",
                "cumulative_saving_yuan",
            ]
        ],
        "q4_price_effect/data/q4_price_effect.csv",
    )

    provenance = {
        "source_root": str(V5_RESULTS),
        "source_sha256": {
            str(comparison_path): sha256(comparison_path),
            str(monthly_path): sha256(monthly_path),
            str(summary_path): sha256(summary_path),
        },
        "selection": {
            "q3_policy_ids": q3_ids,
            "q4_monthly_comparisons": q4_pairs,
        },
        "units": {
            "q3_costs": "million CNY",
            "q4_monthly_and_cumulative_savings": "CNY; positive means the candidate has a lower realized total cost",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source_hashes.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
