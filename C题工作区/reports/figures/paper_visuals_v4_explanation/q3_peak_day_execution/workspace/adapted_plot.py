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
    values = {key: np.array([float(row[key]) for row in data]) for key in (
        "net_load_kwh", "grid_effective_kwh", "emergency_kwh", "battery_net_kwh", "energy_end_actual_kwh"
    )}

    plt.rcParams.update({
        "font.family": "DejaVu Serif", "font.size": 8.9, "axes.labelsize": 10,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9.1, 6.2), sharex=True,
                                      gridspec_kw={"height_ratios": [1.0, 1.0]}, constrained_layout=True)
    top.step(hour, values["net_load_kwh"], where="post", color="#354F6D", linewidth=1.65, label="Actual net load")
    top.step(hour, values["grid_effective_kwh"], where="post", color="#669C78", linewidth=1.55,
             label="Regular grid purchase")
    top.bar(hour, values["emergency_kwh"], width=1/6, align="edge", color="#D88A71", alpha=0.88,
            label="Emergency purchase", zorder=3)
    top.set_ylabel("Interval energy (kWh)")
    top.yaxis.grid(True, color="#E1E1E1", linewidth=0.58)
    top.set_axisbelow(True)
    top.spines[["top", "right"]].set_visible(False)
    top.legend(loc="upper right", frameon=False, ncol=3, fontsize=8.2, handlelength=1.45)

    bottom.bar(hour, values["battery_net_kwh"], width=1/6, align="edge", color="#8BA9C5", alpha=0.86,
               label="Battery discharge (+) / charge (−)", zorder=3)
    bottom.axhline(0, color="#6C6C6C", linewidth=0.75)
    bottom.set_ylabel("Battery interval energy (kWh)")
    bottom.yaxis.grid(True, color="#E1E1E1", linewidth=0.58)
    bottom.set_axisbelow(True)
    bottom.spines[["top"]].set_visible(False)
    secondary = bottom.twinx()
    secondary.step(hour, values["energy_end_actual_kwh"] / 1000, where="post", color="#A3543C", linewidth=1.75,
                   label="End-of-interval SOC")
    secondary.axhline(1.2, color="#8C8C8C", linewidth=0.75, linestyle="--")
    secondary.axhline(10.8, color="#8C8C8C", linewidth=0.75, linestyle="--")
    secondary.set_ylabel("End-of-interval SOC (MWh)")
    secondary.spines[["top"]].set_visible(False)
    handles = [bottom.patches[0], secondary.lines[0]]
    bottom.legend(handles, ["Battery discharge (+) / charge (−)", "End-of-interval SOC"],
                  loc="upper left", frameon=False, fontsize=8.1, handlelength=1.5)
    bottom.set_xlim(0, 24)
    bottom.set_xticks(np.arange(0, 25, 3))
    bottom.set_xlabel("Hour of selected date")
    fig.text(0.5, -0.025,
             "The date is selected solely as the q3_raw day with the largest realized emergency purchase.",
             ha="center", fontsize=8.3, color="#4A4A4A")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
