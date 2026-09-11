"""Render the updated v5 solution-framework diagram for the English paper."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


PROJECT = Path(__file__).resolve().parents[2]
OUT = PROJECT / "reports" / "figures" / "paper_visuals_v3_v5" / "framework_v5" / "outputs"


def box(ax, xy, width, height, text, face, edge="#48627B", fontsize=10.5):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.014",
        linewidth=1.1,
        facecolor=face,
        edgecolor=edge,
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="#1F2D3A",
        linespacing=1.28,
        zorder=3,
    )
    return xy[0] + width / 2, xy[1], xy[0] + width / 2, xy[1] + height


def arrow(ax, start, end, color="#5A7188"):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            transform=ax.transAxes,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.05,
            color=color,
            connectionstyle="arc3,rad=0",
            zorder=1,
        )
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Serif", "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(13.2, 7.1))
    ax.set_axis_off()

    source = box(
        ax,
        (0.27, 0.865),
        0.46,
        0.092,
        "Shared inputs and stated assumptions\nAttachments 1–4 · historical demand/PV/price records",
        "#EEF3F7",
        fontsize=11,
    )
    processed = box(
        ax,
        (0.23, 0.695),
        0.54,
        0.105,
        "Causal data processing\n10-minute alignment · released PV versions · decision-time information cutoffs",
        "#E7F0F5",
        fontsize=10.7,
    )
    core = box(
        ax,
        (0.275, 0.505),
        0.45,
        0.13,
        "Shared v5 direct-purchase core\nHistorical residual scenarios\n+ rolling commitment logic + strict physical executor",
        "#DCE8F0",
        fontsize=10.6,
    )
    arrow(ax, (source[2], source[1]), (processed[2], processed[3]))
    arrow(ax, (processed[2], processed[1]), (core[2], core[3]))

    branches = [
        ((0.015, 0.275), "Problem 1\nDeterministic\nbattery-dispatch MILP\nBaseline schedule", "#F3F5F6"),
        ((0.213, 0.275), "Problem 2\nD112 direct purchase\nMidnight 144-interval plan", "#F8F1E9"),
        ((0.411, 0.275), "Problem 3\nq3_raw\nUpdates at 00/06/12/18", "#EAF3ED"),
        ((0.609, 0.275), "Problem 4-2\nq42_fixed\nFixed planning price\nActual-price settlement", "#F4EDF5"),
        ((0.807, 0.275), "Problem 4-3\nq43_raw_ols\nRaw PV + causal OLS price\nActual-price settlement", "#F4EDF5"),
    ]
    branch_centres = []
    for xy, text, face in branches:
        branch_centres.append(box(ax, xy, 0.178, 0.17, text, face, fontsize=8.85))
    for centre in branch_centres:
        arrow(ax, (core[2], core[1]), (centre[2], centre[3]))

    verified = box(
        ax,
        (0.19, 0.045),
        0.62,
        0.12,
        "Independent verification and deliverables\nPhysical/cost reconstruction · paired within-family comparisons · workbook read-back checks",
        "#E9EEF1",
        fontsize=9.85,
    )
    for centre in branch_centres:
        arrow(ax, (centre[2], centre[1]), (verified[2], verified[3]))

    fig.savefig(OUT / "chart.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "chart.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
