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
        data = sorted(csv.DictReader(handle), key=lambda row: row["month"])
    x = np.arange(len(data))
    monthly = np.array([float(row["raw_vs_no_update_saving_yuan"]) for row in data]) / 1000
    cumulative = np.array([float(row["cumulative_raw_vs_no_update_saving_yuan"]) for row in data]) / 1000
    labels = [row["month"].split("-")[1] for row in data]

    plt.rcParams.update({
        "font.family": "DejaVu Serif", "font.size": 9.5, "axes.labelsize": 10.5,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(8.5, 4.55), constrained_layout=True)
    bars = ax.bar(x, monthly, width=0.67, color="#88A7C4", edgecolor="white", linewidth=0.6,
                  label="Monthly saving", zorder=3)
    ax.axhline(0, color="#6C6C6C", linewidth=0.8, zorder=2)
    ax.set_xticks(x, labels)
    ax.set_xlabel("Month in 2025")
    ax.set_ylabel("Monthly saving (thousand CNY)")
    ax.yaxis.grid(True, color="#DFDFDF", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top"]].set_visible(False)

    secondary = ax.twinx()
    line = secondary.plot(x, cumulative, color="#345F85", marker="o", markersize=4.4, linewidth=2.0,
                          markerfacecolor="white", markeredgewidth=1.15, label="Cumulative saving")[0]
    secondary.set_ylabel("Cumulative saving (thousand CNY)")
    secondary.spines[["top"]].set_visible(False)
    secondary.annotate(f"{cumulative[-1]:+.1f}", xy=(x[-1], cumulative[-1]), xytext=(5, 7),
                       textcoords="offset points", color="#345F85", fontsize=9, fontweight="bold")
    ax.legend([bars, line], ["Monthly saving", "Cumulative saving"], loc="upper left", frameon=False,
              handlelength=1.55)
    fig.text(0.5, -0.04,
             "Positive saving: q3_raw has lower realized cost than q3_no_update in the same month.",
             ha="center", fontsize=8.8, color="#4A4A4A")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
