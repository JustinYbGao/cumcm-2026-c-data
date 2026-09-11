from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main() -> None:
    data_path = Path(os.environ.get("DATA_PATH", sys.argv[1]))
    output_dir = Path(os.environ.get("OUTPUT_DIR", sys.argv[2]))
    output_dir.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(data_path).sort_values("policy_order")

    plt.rcParams.update({
        "font.family": "DejaVu Serif",
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 11,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(8.1, 5.25))
    fig.subplots_adjust(left=0.105, right=0.985, top=0.78, bottom=0.22)
    x = np.arange(len(data))
    contract = data["contract_cost_million_cny"].to_numpy()
    emergency = data["emergency_cost_million_cny"].to_numpy()
    total = data["total_cost_million_cny"].to_numpy()

    selected_index = int(np.where(data["selected"].to_numpy())[0][0])
    ax.axvspan(selected_index - 0.48, selected_index + 0.48, color="#EAF0F6", zorder=0)
    ax.bar(x, contract, width=0.62, color="#5F7FA3", edgecolor="white", linewidth=0.8,
           label="Contract cost", zorder=3)
    ax.bar(x, emergency, width=0.62, bottom=contract, color="#D98B73", edgecolor="white",
           linewidth=0.8, label="Emergency cost", zorder=3)
    for index, value in enumerate(total):
        ax.text(index, value + 0.055, f"{value:.3f}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x, data["policy_label"])
    ax.set_ylabel("Realized cost (million CNY)")
    ax.set_ylim(0, max(total) + 0.32)
    ax.yaxis.grid(True, color="#D9D9D9", linewidth=0.65, alpha=0.9)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.085), frameon=False, ncol=2, handlelength=1.35)
    ax.text(selected_index, -0.11, "selected policy", transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=8.8, color="#40566F")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
