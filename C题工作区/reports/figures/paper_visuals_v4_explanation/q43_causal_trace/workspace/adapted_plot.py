from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
def main() -> None:
    data_path = Path(os.environ.get("DATA_PATH", sys.argv[1]))
    output_dir = Path(os.environ.get("OUTPUT_DIR", sys.argv[2]))
    output_dir.mkdir(parents=True, exist_ok=True)
    with data_path.open(newline="", encoding="utf-8") as handle:
        data = sorted(csv.DictReader(handle), key=lambda row: int(row["slot_id"]))
    hour = np.array([float(row["hour"]) for row in data])
    def numeric(name: str) -> np.ndarray:
        return np.array([float(row[name]) if row[name] else np.nan for row in data])
    colours = {0: "#64748B", 6: "#5B8F80", 12: "#4B76A3", 18: "#C27A59"}

    plt.rcParams.update({
        "font.family": "DejaVu Serif", "font.size": 8.9, "axes.labelsize": 10,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9.25, 6.3), sharex=True, constrained_layout=True)
    top.step(hour, numeric("actual_price_yuan_per_kwh"), where="post", color="#303030", linewidth=1.75,
             label="Actual settlement price", zorder=4)
    for issue in (0, 6, 12, 18):
        top.step(hour, numeric(f"price_forecast_{issue}_yuan_per_kwh"), where="post", color=colours[issue],
                 linewidth=1.15, linestyle="--", label=f"{issue:02d}:00 price forecast")
    top.set_ylabel("Price (CNY/kWh)")
    top.yaxis.grid(True, color="#E1E1E1", linewidth=0.58)
    top.set_axisbelow(True)
    top.spines[["top", "right"]].set_visible(False)
    top.legend(loc="upper right", frameon=False, ncol=2, fontsize=7.9, handlelength=1.6)

    for issue in (0, 6, 12, 18):
        bottom.step(hour, numeric(f"grid_plan_{issue}_kwh"), where="post", color=colours[issue],
                    linewidth=1.2, linestyle="--", label=f"{issue:02d}:00 plan")
    bottom.step(hour, numeric("executed_grid_kwh"), where="post", color="#303030", linewidth=1.8,
                label="Executed regular purchase", zorder=4)
    for issue in (6, 12, 18):
        bottom.axvline(issue, color="#A8A8A8", linewidth=0.7, linestyle=":", zorder=1)
    bottom.set_ylabel("Interval grid energy (kWh)")
    bottom.set_xlabel("Hour of 2025-07-14")
    bottom.yaxis.grid(True, color="#E1E1E1", linewidth=0.58)
    bottom.set_axisbelow(True)
    bottom.spines[["top", "right"]].set_visible(False)
    bottom.legend(loc="upper right", frameon=False, ncol=2, fontsize=7.9, handlelength=1.6)
    bottom.set_xlim(0, 24)
    bottom.set_xticks(np.arange(0, 25, 3))
    fig.text(0.5, -0.025,
             "Forecast and plan segments start only at their release time; price is settled at the actual value.",
             ha="center", fontsize=8.3, color="#4A4A4A")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
