from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_groups(path: Path):
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[row["comparison_id"]].append(row)
    return groups


def main() -> None:
    data_path = Path(os.environ.get("DATA_PATH", sys.argv[1]))
    output_dir = Path(os.environ.get("OUTPUT_DIR", sys.argv[2]))
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = read_groups(data_path)
    order = ["q42_ols_vs_fixed", "q43_ols_vs_fixed"]
    colours = [("#89A6C3", "#3F638A"), ("#D9A07D", "#A9533C")]

    plt.rcParams.update({
        "font.family": "DejaVu Serif",
        "font.size": 9.5,
        "axes.labelsize": 10.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.35), sharey=False, constrained_layout=True)
    for ax, comparison_id, (bar_colour, line_colour) in zip(axes, order, colours):
        rows = sorted(groups[comparison_id], key=lambda item: item["month"])
        months = [row["month"].split("-")[1] for row in rows]
        monthly = np.array([float(row["monthly_saving_yuan"]) for row in rows]) / 1000
        cumulative = np.array([float(row["cumulative_saving_yuan"]) for row in rows]) / 1000
        x = np.arange(len(rows))

        bars = ax.bar(x, monthly, width=0.68, color=bar_colour, edgecolor="white", linewidth=0.55,
                      label="Monthly saving", zorder=3)
        ax.axhline(0, color="#777777", linewidth=0.75, zorder=2)
        ax.set_xticks(x, months)
        ax.set_xlabel("Month in 2025")
        ax.set_ylabel("Monthly saving (thousand CNY)")
        ax.yaxis.grid(True, color="#DEDEDE", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines[["top"]].set_visible(False)

        secondary = ax.twinx()
        secondary.plot(x, cumulative, color=line_colour, marker="o", markersize=4.2, linewidth=2.0,
                       markerfacecolor="white", markeredgewidth=1.15, label="Cumulative saving")
        secondary.set_ylabel("Cumulative saving (thousand CNY)")
        secondary.spines[["top"]].set_visible(False)
        secondary.annotate(f"{cumulative[-1]:+.2f}", xy=(x[-1], cumulative[-1]),
                           xytext=(4, 7 if cumulative[-1] >= 0 else -13), textcoords="offset points",
                           color=line_colour, fontsize=9, fontweight="bold")
        handles = [bars, secondary.lines[0]]
        ax.legend(handles, ["Monthly saving", "Cumulative saving"], loc="upper left", frameon=False,
                  fontsize=8.4, handlelength=1.45)
        title = rows[0]["comparison_label"].replace(" − ", " vs. ")
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", pad=6)

    fig.text(0.5, -0.045, "Positive saving: the OLS planning-price candidate has lower realized cost.",
             ha="center", fontsize=9, color="#4A4A4A")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
