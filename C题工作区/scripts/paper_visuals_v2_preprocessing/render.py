"""Render paper-ready data-preparation figures from immutable processed inputs.

This script only copies input snapshots and writes derived visual assets beneath
reports/figures/paper_visuals_v2_preprocessing/.  It never rewrites processed
data, raw workbooks, results, or templates.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd


WORK = Path(__file__).resolve().parents[2]
OUT = WORK / "reports" / "figures" / "paper_visuals_v2_preprocessing"
DATA = OUT / "data"
PIPELINE = OUT / "data_pipeline" / "outputs"
COVERAGE = OUT / "data_coverage" / "outputs"

INPUTS = {
    "actual_10min.csv": WORK / "data" / "processed" / "actual_10min.csv",
    "pv_forecast_hourly.csv": WORK / "data" / "processed" / "pv_forecast_hourly.csv",
    "forecast_coverage.csv": WORK / "data" / "interim" / "forecast_coverage.csv",
    "numeric_summary.csv": WORK / "reports" / "numeric_summary.csv",
    "quality_report.md": WORK / "reports" / "quality_report.md",
    "validation_all.json": WORK / "reports" / "validation_all.json",
    "validation_forecast_diagnostics.json": WORK / "reports" / "validation_forecast_diagnostics.json",
}

COLORS = {
    "navy": "#19324a",
    "blue": "#2e6f95",
    "teal": "#138a8a",
    "orange": "#e58a2b",
    "gold": "#f1bf4b",
    "red": "#b24c4c",
    "slate": "#5c6b73",
    "light": "#edf3f5",
    "light_blue": "#e5f0f7",
    "light_orange": "#fff0df",
    "light_teal": "#e2f2ef",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_inputs() -> dict[str, str]:
    DATA.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, source in INPUTS.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = DATA / name
        shutil.copy2(source, destination)
        hashes[name] = sha256(source)
    return hashes


def add_box(ax, xy, width, height, title, body, *, face, edge=COLORS["navy"], title_color=COLORS["navy"], fs=10):
    x, y = xy
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.15, edgecolor=edge, facecolor=face,
        transform=ax.transAxes, clip_on=False,
    )
    ax.add_patch(box)
    ax.text(x + 0.018, y + height - 0.032, title, transform=ax.transAxes,
            ha="left", va="top", fontsize=fs + 0.6, weight="bold", color=title_color)
    ax.text(x + 0.018, y + height - 0.075, body, transform=ax.transAxes,
            ha="left", va="top", fontsize=fs, linespacing=1.15, color=COLORS["navy"])


def arrow(ax, x1, y1, x2, y2, color=COLORS["slate"]):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), transform=ax.transAxes,
        arrowstyle="-|>", mutation_scale=13, linewidth=1.25, color=color,
        connectionstyle="arc3,rad=0",
    ))


def render_pipeline(facts: dict):
    PIPELINE.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(15.2, 9.4))
    fig.patch.set_facecolor("white")
    ax.set_axis_off()
    ax.text(0.02, 0.975, "Data preparation and audit pipeline", transform=ax.transAxes,
            fontsize=17, weight="bold", color=COLORS["navy"], va="top")
    ax.text(0.02, 0.94,
            "Every transformation retains the original time order; numerical observations are not automatically smoothed, deleted, or imputed.",
            transform=ax.transAxes, fontsize=10.2, color=COLORS["slate"], va="top")

    # Source layer.
    add_box(ax, (0.03, 0.70), 0.205, 0.145, "Attachment 1", "Fixed tariff, load, and\nPV forecast\n144 ten-minute intervals", face=COLORS["light_blue"], fs=8.7)
    add_box(ax, (0.03, 0.50), 0.205, 0.145, "Attachment 2", "Observed load and PV\n365 days × 144 intervals\n52,560 time-keyed records", face=COLORS["light_blue"], fs=8.7)
    add_box(ax, (0.03, 0.30), 0.205, 0.145, "Attachment 3", "PV forecast versions\n4 releases/day × 24 targets\n35,040 version–target records", face=COLORS["light_blue"], fs=8.7)
    add_box(ax, (0.03, 0.10), 0.205, 0.145, "Attachment 4", "Time-varying electricity price\n365 days × 144 intervals\n52,560 time-keyed records", face=COLORS["light_blue"], fs=8.7)

    # Standardization layer.
    add_box(ax, (0.34, 0.62), 0.265, 0.225, "Time and unit standardization",
            "• Parse ordered interval-end labels\n• Keep the 10-minute grid unchanged\n• Convert interval-average kW to kWh\n  using Δt = 1/6 h\n• Retain forecast issue time and target time", face=COLORS["light_teal"], edge=COLORS["teal"])
    add_box(ax, (0.34, 0.33), 0.265, 0.205, "Structural-label handling",
            f"• Carry repeated forecast dates downward\n  for {facts['structural_blank_dates']:,} blank source labels\n• Do not alter PV forecast values\n• Record each label transformation\n• Keep the original row order", face=COLORS["light_orange"], edge=COLORS["orange"])
    add_box(ax, (0.34, 0.10), 0.265, 0.145, "Key and value audit",
            "• Validate date–time keys and one-to-one joins\n• Keep valid zero PV and signed net-load values\n• Flag large jumps for review; do not auto-delete", face=COLORS["light"], edge=COLORS["slate"], fs=9.2)

    # Output layer.
    add_box(ax, (0.70, 0.64), 0.265, 0.205, "Decision-ready scheduling inputs",
            "Q1 daily profile: 144 intervals\nActual operating grid: 52,560 records\nHourly PV forecasts: 35,040 records\nConverted PV forecasts: 210,234 records", face="#e9edf6", edge=COLORS["blue"])
    add_box(ax, (0.70, 0.36), 0.265, 0.185, "Coverage boundary retained",
            "One first forecast release has 138\nconverted intervals because no prior\nendpoint is available. No first-hour\nforecast is invented; 1,459 releases\nretain 144 intervals.", face="#f9ecec", edge=COLORS["red"])
    add_box(ax, (0.70, 0.10), 0.265, 0.165, "Cross-problem interface",
            "Shared time grid, energy unit, source\ntraceability, and SOC convention feed\nProblems 1–4. Strategy branches retain\nseparate decision records and SOC paths.", face=COLORS["light_teal"], edge=COLORS["teal"])

    # Arrows with a convergent source flow.
    for y in (0.772, 0.572, 0.372, 0.172):
        arrow(ax, 0.235, y, 0.34, 0.735 if y > 0.60 else (0.432 if y > 0.20 else 0.172))
    arrow(ax, 0.605, 0.735, 0.70, 0.742)
    arrow(ax, 0.605, 0.432, 0.70, 0.452)
    arrow(ax, 0.605, 0.172, 0.70, 0.182)
    arrow(ax, 0.835, 0.64, 0.835, 0.545, color=COLORS["blue"])
    arrow(ax, 0.835, 0.36, 0.835, 0.265, color=COLORS["blue"])

    ax.text(0.03, 0.03,
            f"Audit evidence: {facts['base_checks_passed']}/{facts['base_checks_total']} base checks and "
            f"{facts['forecast_checks_passed']}/{facts['forecast_checks_total']} forecast-diagnostic checks passed; "
            "this confirms the stated processing checks, not forecasting accuracy.",
            transform=ax.transAxes, fontsize=9.1, color=COLORS["slate"], va="bottom")
    for suffix in ("png", "svg"):
        fig.savefig(PIPELINE / f"chart.{suffix}", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_coverage(facts: dict, month_summary: pd.DataFrame):
    COVERAGE.mkdir(parents=True, exist_ok=True)
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(15.2, 6.6), gridspec_kw={"width_ratios": [0.95, 1.2]})
    fig.patch.set_facecolor("white")

    records = pd.DataFrame({
        "Data set": ["Q1 daily inputs", "Actual operating grid", "Hourly PV forecasts", "10-min PV forecasts"],
        "Records": [facts["q1_records"], facts["actual_records"], facts["hourly_records"], facts["converted_records"]],
        "color": [COLORS["gold"], COLORS["blue"], COLORS["orange"], COLORS["teal"]],
    })
    records = records.iloc[::-1]
    bars = ax_left.barh(records["Data set"], records["Records"], color=records["color"], height=0.58)
    ax_left.set_title("Record coverage after preprocessing", loc="left", fontsize=13, weight="bold", color=COLORS["navy"], pad=12)
    ax_left.set_xlabel("Records retained (count)")
    ax_left.grid(axis="x", color="#d8e0e5", linewidth=0.7)
    ax_left.set_axisbelow(True)
    ax_left.spines[["top", "right", "left"]].set_visible(False)
    ax_left.tick_params(axis="y", length=0)
    for bar, value in zip(bars, records["Records"]):
        ax_left.text(bar.get_width() + facts["converted_records"] * 0.018,
                     bar.get_y() + bar.get_height() / 2, f"{value:,}", va="center", fontsize=10, color=COLORS["navy"], weight="bold")
    ax_left.set_xlim(0, facts["converted_records"] * 1.20)
    ax_left.text(0, -0.18,
                 "Converted forecast coverage: one release has 138 intervals;\nall other 1,459 releases have 144 intervals.",
                 transform=ax_left.transAxes, fontsize=9.3, color=COLORS["slate"], va="top")

    labels = month_summary["month_label"].tolist()
    zero = month_summary["zero_pv_observations"].to_numpy()
    positive = month_summary["positive_pv_observations"].to_numpy()
    ax_right.bar(labels, zero, label="Valid zero PV retained", color=COLORS["gold"], width=0.72)
    ax_right.bar(labels, positive, bottom=zero, label="Positive PV retained", color=COLORS["teal"], width=0.72)
    ax_right.set_title("Actual PV observations retained by month", loc="left", fontsize=13, weight="bold", color=COLORS["navy"], pad=30)
    ax_right.set_xlabel("Month in 2025")
    ax_right.set_ylabel("Ten-minute observations (count)")
    ax_right.grid(axis="y", color="#d8e0e5", linewidth=0.7)
    ax_right.set_axisbelow(True)
    ax_right.spines[["top", "right"]].set_visible(False)
    ax_right.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False, fontsize=9.2)
    ax_right.text(0.01, 1.012,
                  f"All {facts['actual_records']:,} numerical operating-grid records were present, finite, and nonnegative; "
                  f"{facts['pv_zero_observations']:,} zero-PV observations were retained.",
                  transform=ax_right.transAxes, fontsize=8.9, color=COLORS["slate"], va="bottom")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.78, bottom=0.25, wspace=0.34)
    for suffix in ("png", "svg"):
        fig.savefig(COVERAGE / f"chart.{suffix}", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    hashes = snapshot_inputs()
    actual = pd.read_csv(DATA / "actual_10min.csv", parse_dates=["interval_start"])
    hourly = pd.read_csv(DATA / "pv_forecast_hourly.csv", parse_dates=["issue_time", "target_time"])
    forecast_coverage = pd.read_csv(DATA / "forecast_coverage.csv")
    base_checks = json.loads((DATA / "validation_all.json").read_text(encoding="utf-8"))
    forecast_checks = json.loads((DATA / "validation_forecast_diagnostics.json").read_text(encoding="utf-8"))

    actual["month"] = actual["interval_start"].dt.month
    month_summary = actual.groupby("month", as_index=False).agg(
        ten_minute_observations=("pv_actual_kw", "size"),
        zero_pv_observations=("pv_actual_kw", lambda x: int((x == 0).sum())),
        positive_pv_observations=("pv_actual_kw", lambda x: int((x > 0).sum())),
    )
    month_summary["month_label"] = pd.to_datetime(month_summary["month"], format="%m").dt.strftime("%b")
    month_summary.to_csv(DATA / "actual_pv_monthly_retention.csv", index=False)

    # date_was_filled repeats each source row 24 times; count source rows once.
    source_rows = hourly[["source_row", "date_was_filled"]].drop_duplicates("source_row")
    facts = {
        "q1_records": 144,
        "actual_records": int(len(actual)),
        "hourly_records": int(len(hourly)),
        "converted_records": int(forecast_coverage["interval_count"].sum()),
        "releases_with_138": int((forecast_coverage["interval_count"] == 138).sum()),
        "releases_with_144": int((forecast_coverage["interval_count"] == 144).sum()),
        "structural_blank_dates": int(source_rows["date_was_filled"].sum()),
        "pv_zero_observations": int((actual["pv_actual_kw"] == 0).sum()),
        "base_checks_total": len(base_checks),
        "base_checks_passed": sum(bool(item["passed"]) for item in base_checks),
        "forecast_checks_total": len(forecast_checks),
        "forecast_checks_passed": sum(bool(item["passed"]) for item in forecast_checks),
        "source_sha256": hashes,
    }
    (OUT / "plot_facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    render_pipeline(facts)
    render_coverage(facts, month_summary)
    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main()
