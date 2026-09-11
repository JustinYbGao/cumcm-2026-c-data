"""Create traceable English paper figures from the frozen Problem 2 result files.

The script is deliberately limited to an overview and Problem 2 result figures.
Problem 1, 3 and 4 use their existing independently reviewed ModelViz data and
renderers in the same paper-visuals package.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd


WORK = Path(__file__).resolve().parents[2]
RESULTS = WORK / "results" / "q2_direct_v4"
OUTPUT = WORK / "reports" / "figures" / "paper_visuals_v1"

plt.rcParams.update(
    {
        "font.family": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10.5,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
        "savefig.facecolor": "white",
        "svg.hashsalt": "cumcm-paper-visuals-v1",
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_figure(fig: plt.Figure, name: str, facts: dict) -> None:
    task = OUTPUT / name
    out = task / "outputs"
    workspace = task / "workspace"
    out.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(out / f"chart.{ext}", dpi=300, bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    (workspace / "plot_facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")


def copy_source(source: Path, task: str, new_name: str | None = None) -> str:
    target = OUTPUT / task / "data"
    target.mkdir(parents=True, exist_ok=True)
    destination = target / (new_name or source.name)
    shutil.copy2(source, destination)
    return sha256(source)


def make_workflow() -> None:
    fig, ax = plt.subplots(figsize=(12.0, 5.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5)
    ax.axis("off")
    fig.suptitle("Integrated scheduling and verification framework", x=0.5, y=0.98, fontsize=17)

    colors = {"input": "#dbeaf7", "process": "#e8e4f2", "core": "#d9ead3", "question": "#fce5cd", "audit": "#d9eaf7"}

    def box(x, y, w, h, text, color, fontsize=10):
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.035,rounding_size=0.08", facecolor=color, edgecolor="#55616d", linewidth=0.9
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)

    def arrow(x1, y1, x2, y2, label=None, dashed=False):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.05, color="#53616c", linestyle="--" if dashed else "-")
        )
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.18, label, ha="center", va="bottom", fontsize=8.2, color="#49545d")

    box(0.25, 3.55, 2.0, 0.85, "Attachments 1-4\n+ battery parameters", colors["input"])
    box(2.7, 3.55, 2.05, 0.85, "Time mapping, units\n+ and source-key audit", colors["process"])
    box(5.15, 3.55, 2.2, 0.85, "Shared physical core\n+ balance, SOC and limits", colors["core"])
    box(7.75, 3.55, 1.7, 0.85, "Independent ledger\n+ reconstruction", colors["audit"])
    box(9.85, 3.55, 1.9, 0.85, "Feasibility and\n+ cost checks", colors["audit"])
    arrow(2.25, 3.98, 2.7, 3.98)
    arrow(4.75, 3.98, 5.15, 3.98)
    arrow(7.35, 3.98, 7.75, 3.98)
    arrow(9.45, 3.98, 9.85, 3.98)

    qs = [
        (0.35, "Problem 1\n+ fixed-input MILP"),
        (3.2, "Problem 2\n+ causal direct purchase"),
        (6.05, "Problem 3\n+ rolling PV updates"),
        (8.9, "Problem 4\n+ causal-price branches"),
    ]
    for x, label in qs:
        box(x, 1.55, 2.2, 0.9, label, colors["question"], 9.6)
        arrow(6.25, 3.55, x + 1.1, 2.45)
    arrow(2.55, 1.99, 3.2, 1.99, "shared execution rules")
    arrow(5.4, 1.99, 6.05, 1.99, "frozen original branch", dashed=True)
    arrow(8.25, 1.99, 8.9, 1.99, "price information", dashed=True)
    box(3.2, 0.25, 2.2, 0.7, "D112 historical-scenario extension\n+ reported only for Problem 2", "#fff2cc", 8.8)
    arrow(4.3, 1.55, 4.3, 0.95, dashed=True)
    ax.text(6.0, 0.52, "No policy borrows future realizations, terminal SOC,\n+ or a post-hoc purchase vector from another branch.", ha="left", va="center", fontsize=9, color="#59636f")
    save_figure(
        fig,
        "overall_framework",
        {
            "source": "Problem_Restatement_EN.md Sections 2 and 5; no numerical values.",
            "scope": "diagram of declared information and validation flow",
        },
    )


def load_q2() -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    paths = {
        "D112 direct purchase": RESULTS / "runs" / "D112" / "daily.csv",
        "X_strong risk purchase": RESULTS / "references" / "X_strong_morning85" / "daily.csv",
        "January-selected policy": RESULTS / "references" / "B0" / "daily.csv",
        "Seasonal baseline": RESULTS / "references" / "B1" / "daily.csv",
    }
    frames = {label: pd.read_csv(path) for label, path in paths.items()}
    for label, path in paths.items():
        copy_source(path, "q2_policy", f"{label.replace(' ', '_')}.csv")
    bootstrap = pd.read_csv(RESULTS / "block_bootstrap.csv")
    wins = pd.read_csv(RESULTS / "win_loss_counts.csv")
    copy_source(RESULTS / "block_bootstrap.csv", "q2_uncertainty")
    copy_source(RESULTS / "win_loss_counts.csv", "q2_uncertainty")
    return frames, bootstrap, wins


def make_q2_policy(frames: dict[str, pd.DataFrame]) -> None:
    order = list(frames)
    summary = pd.DataFrame(
        {
            "policy": order,
            "regular": [frames[p]["planned_cost_yuan"].sum() for p in order],
            "emergency": [frames[p]["emergency_cost_yuan"].sum() for p in order],
        }
    )
    summary["total"] = summary["regular"] + summary["emergency"]
    d112 = frames["D112 direct purchase"].copy()
    xstrong = frames["X_strong risk purchase"].copy()
    d112["month"] = pd.to_datetime(d112["date"]).dt.strftime("%b")
    xstrong["month"] = pd.to_datetime(xstrong["date"]).dt.strftime("%b")
    months = ["Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    saving = xstrong.groupby("month")["total_cost_yuan"].sum().reindex(months) - d112.groupby("month")["total_cost_yuan"].sum().reindex(months)

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.1), gridspec_kw={"width_ratios": [1.05, 1.35]}, layout="constrained")
    fig.suptitle("Problem 2 | Cost comparison under fixed-tariff historical replay", x=0.055, y=0.99, ha="left", fontsize=16.5)
    fig.get_layout_engine().set(rect=(0, 0.105, 1, 0.855))
    x = np.arange(len(order))
    a = axes[0]
    a.bar(x, summary["regular"] / 1e6, color="#78a6c8", label="Regular purchase")
    a.bar(x, summary["emergency"] / 1e6, bottom=summary["regular"] / 1e6, color="#d9875f", label="Emergency purchase")
    a.set_xticks(x, ["D112", "X_strong", "January\nselected", "Seasonal"], fontsize=9)
    a.set_ylabel("Realized cost (million CNY)")
    a.set_title("(a) Annual bill components", loc="left", pad=8, fontsize=12)
    a.grid(axis="y", color="#d5dbe0", lw=0.5)
    a.set_axisbelow(True)
    a.legend(loc="upper left", fontsize=9)
    for i, value in enumerate(summary["total"] / 1e6):
        a.text(i, value + 0.18, f"{value:.3f}", ha="center", va="bottom", fontsize=8.8)

    b = axes[1]
    colors = ["#4b9cd3" if value >= 0 else "#d9875f" for value in saving / 1000]
    b.bar(np.arange(11), saving / 1000, color=colors, width=0.67)
    b.axhline(0, color="#505a64", lw=0.8)
    b.set_xticks(np.arange(11), months)
    b.set_ylabel("Savings versus X_strong (thousand CNY)")
    b.set_title("(b) D112 monthly total-cost difference", loc="left", pad=8, fontsize=12)
    b.grid(axis="y", color="#d5dbe0", lw=0.5)
    b.set_axisbelow(True)
    fig.text(0.055, 0.018, "Positive savings indicate a lower realized bill. The annual D112-X_strong difference is CNY 80,389.78; this is an observed-path comparison.", fontsize=9.2, color="#59636f")
    save_figure(
        fig,
        "q2_policy",
        {
            "source_sha256": {
                label: sha256(RESULTS / ("runs/D112/daily.csv" if label == "D112 direct purchase" else f"references/{ {'X_strong risk purchase':'X_strong_morning85','January-selected policy':'B0','Seasonal baseline':'B1'}[label] }/daily.csv"))
                for label in order
            },
            "annual_totals_yuan": summary.set_index("policy")["total"].to_dict(),
            "monthly_saving_total_yuan": float(saving.sum()),
        },
    )


def make_q2_uncertainty(bootstrap: pd.DataFrame, wins: pd.DataFrame) -> None:
    ci = bootstrap.loc[
        (bootstrap["policy"] == "D112")
        & (bootstrap["baseline"] == "X_strong_morning85")
        & (bootstrap["component"] == "total_cost_yuan")
    ].sort_values("block_days")
    counts = wins.loc[(wins["policy"] == "D112") & (wins["baseline"] == "X_strong_morning85")].iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw={"width_ratios": [1.25, 1]}, layout="constrained")
    fig.suptitle("Problem 2 | Historical comparison evidence for D112", x=0.055, y=0.99, ha="left", fontsize=16.5)
    fig.get_layout_engine().set(rect=(0, 0.12, 1, 0.80))
    a = axes[0]
    y = np.arange(len(ci))
    point = ci["saving_yuan"].to_numpy() / 1000
    low = ci["ci95_low_yuan"].to_numpy() / 1000
    high = ci["ci95_high_yuan"].to_numpy() / 1000
    a.errorbar(point, y, xerr=np.vstack((point - low, high - point)), fmt="o", color="#2878b5", ecolor="#6e9bbd", capsize=4, lw=1.5)
    a.axvline(0, color="#505a64", lw=0.8)
    a.set_yticks(y, [f"{int(days)}-day blocks" for days in ci["block_days"]])
    a.set_xlabel("Total-cost saving versus X_strong (thousand CNY)")
    a.set_title("(a) 95% block-resampling intervals", loc="left", pad=8, fontsize=12)
    a.grid(axis="x", color="#d5dbe0", lw=0.5)
    a.set_axisbelow(True)
    for xx, yy, lo, hi in zip(point, y, low, high):
        a.text(hi + 5, yy, f"[{lo:.1f}, {hi:.1f}]", va="center", fontsize=8.4)

    b = axes[1]
    names = ["Lower-cost days", "Higher-cost days", "Emergency-cost\nworse days"]
    values = [int(counts["total_winning_days"]), int(counts["total_losing_days"]), int(counts["emergency_worse_days"])]
    bars = b.bar(names, values, color=["#68b48a", "#b7bdc4", "#d9875f"], width=0.62)
    b.set_ylabel("Days in the 334-day replay")
    b.set_ylim(0, max(values) * 1.22)
    b.set_title("(b) Day-level comparison with X_strong", loc="left", pad=8, fontsize=12)
    b.grid(axis="y", color="#d5dbe0", lw=0.5)
    b.set_axisbelow(True)
    for bar, value in zip(bars, values):
        b.text(bar.get_x() + bar.get_width() / 2, value + 7, str(value), ha="center", va="bottom")
    fig.text(0.055, 0.018, "Both total-cost intervals include zero. The resampling describes the observed historical path and is not a global-optimality, significance, or future-year guarantee.", fontsize=9.1, color="#59636f")
    save_figure(
        fig,
        "q2_uncertainty",
        {
            "bootstrap_source_sha256": sha256(RESULTS / "block_bootstrap.csv"),
            "win_loss_source_sha256": sha256(RESULTS / "win_loss_counts.csv"),
            "intervals_yuan": ci[["block_days", "saving_yuan", "ci95_low_yuan", "ci95_high_yuan"]].to_dict(orient="records"),
            "day_counts": {key: int(counts[key]) for key in ("total_winning_days", "total_losing_days", "emergency_worse_days")},
        },
    )


def main() -> None:
    frames, bootstrap, wins = load_q2()
    make_workflow()
    make_q2_policy(frames)
    make_q2_uncertainty(bootstrap, wins)


if __name__ == "__main__":
    main()
