"""Select ModelViz templates and adapt them to the three verified v5 inputs."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from src.services.final_template_selection_pipeline import run_final_template_selection_pipeline
from src.services.template_adaptation_pipeline import run_template_adaptation_pipeline


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "reports" / "figures" / "paper_visuals_v4_explanation"
PYTHON = "/Users/mike/Documents/Codex/2026-09-10/zhe/work/notebook-env/bin/python3"


Q3_MONTHLY_CODE = r'''from __future__ import annotations

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
'''


Q3_PEAK_CODE = r'''from __future__ import annotations

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
                  loc="upper right", frameon=False, fontsize=8.1, handlelength=1.5)
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
'''


Q43_TRACE_CODE = r'''from __future__ import annotations

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
'''


TASKS = {
    "q3_monthly_saving": {
        "data": ROOT / "q3_monthly_saving" / "data" / "q3_monthly_saving.csv",
        "template_id": "trd_dual_axis_bar_line",
        "template_name": "双Y轴柱状折线时间序列图",
        "summary": "Eleven chronological monthly raw-PV-versus-no-update savings with a cumulative total.",
        "features": ["Eleven monthly observations", "Signed monthly saving", "Chronological cumulative saving"],
        "columns": ["month", "raw_vs_no_update_saving_yuan", "cumulative_raw_vs_no_update_saving_yuan"],
        "code": Q3_MONTHLY_CODE,
        "reason": "A bar-and-line time-series separates signed monthly variation from the accumulated historical comparison.",
    },
    "q3_peak_day_execution": {
        "data": ROOT / "q3_peak_day_execution" / "data" / "q3_peak_day_execution.csv",
        "template_id": "trd_dual_axis_bar_line",
        "template_name": "双Y轴柱状折线时间序列图",
        "summary": "One traceably selected 144-interval q3_raw stress day with physical energy flows and state of charge.",
        "features": ["One 144-interval day", "Energy balance components", "Battery state trajectory"],
        "columns": ["hour", "net_load_kwh", "grid_effective_kwh", "emergency_kwh", "battery_net_kwh", "energy_end_actual_kwh"],
        "code": Q3_PEAK_CODE,
        "reason": "A two-panel composite time series presents raw interval-level dispatch and SOC without smoothing or resampling.",
    },
    "q43_causal_trace": {
        "data": ROOT / "q43_causal_trace" / "data" / "q43_causal_trace.csv",
        "template_id": "trd_dual_axis_bar_line",
        "template_name": "双Y轴柱状折线时间序列图",
        "summary": "A predeclared causal-audit day with actual price, release-specific price forecasts, plan versions, and executed purchase.",
        "features": ["Four causally released forecast versions", "Actual settlement price", "Stepwise purchase plan revisions"],
        "columns": [
            "hour", "actual_price_yuan_per_kwh", "price_forecast_0_yuan_per_kwh", "price_forecast_6_yuan_per_kwh",
            "price_forecast_12_yuan_per_kwh", "price_forecast_18_yuan_per_kwh", "grid_plan_0_kwh", "grid_plan_6_kwh",
            "grid_plan_12_kwh", "grid_plan_18_kwh", "executed_grid_kwh",
        ],
        "code": Q43_TRACE_CODE,
        "reason": "A two-panel composite time series makes release-time availability and the associated grid-plan revisions legible on the same audit day.",
    },
}


def runnable(value):
    return RunnableLambda(lambda _, result=value: result)


def main() -> None:
    reports: dict[str, object] = {}
    for task_name, task in TASKS.items():
        workspace = ROOT / task_name / "workspace"
        selection = {
            "dataset_summary": task["summary"],
            "observed_data_features": task["features"],
            "relevant_columns": task["columns"],
            "candidate_comparisons": [],
            "selected_template_id": task["template_id"],
            "selected_template_name": task["template_name"],
            "alternative_template_ids": ["trd_dual_axis_bar_line", "trd_composite_line_bar_dual_axis"],
            "selection_reason": task["reason"],
            "data_support_reason": "All charted columns are present in the prepared traceable input table.",
            "data_warnings": ["The figures are descriptive historical-replay evidence, not a future-performance or significance claim."],
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": "",
        }
        plan = {
            "template_id": task["template_id"],
            "template_name": task["template_name"],
            "plot_goal": task["summary"],
            "selected_columns": task["columns"],
            "column_mappings": [
                {"data_column": column, "template_role": "plotted time-series field", "reason": "Verified input field required by the explanatory trace."}
                for column in task["columns"]
            ],
            "required_preprocessing": ["Sort by chronological month or ten-minute slot; retain source values without smoothing."],
            "required_dependencies": ["matplotlib", "numpy"],
            "layout_elements_to_preserve": ["time-series comparison", "compact legends", "clean scientific axes"],
            "style_elements_to_preserve": ["serif scientific typography", "muted palette", "light grid"],
            "elements_allowed_to_change": ["English labels", "replace template demonstration data with verified v5 fields", "use two panels when the data need distinct physical scales"],
            "title_plan": "No internal title; the manuscript caption supplies the figure title.",
            "axis_plan": "Label all physical quantities and time boundaries explicitly.",
            "legend_plan": "Use only labels required to distinguish reported data series.",
            "annotation_plan": "Show only predeclared date-selection or causality notes, with no significance claim.",
            "output_formats": ["png", "svg"],
            "warnings": ["No smoothing, interpolation, or unsupported causal inference is introduced by the figure."],
            "can_proceed": True,
            "clarification_question": "",
        }
        selected = run_final_template_selection_pipeline(
            runnable(selection), str(task["data"]),
            requirement_path=str(workspace / "user_requirement.json"),
            candidate_path=str(workspace / "candidate_templates.json"),
            output_path=str(workspace / "final_template_selection.json"),
            dataset_context_path=str(workspace / "dataset_context.json"),
        )
        adapted = run_template_adaptation_pipeline(
            runnable(plan),
            runnable({
                "adapted_code": task["code"],
                "changes_summary": ["Replaced demonstration data with the verified explanatory input table.", "Preserved the selected time-series template family in an English paper style."],
                "preserved_style_elements": plan["style_elements_to_preserve"] + plan["layout_elements_to_preserve"],
                "changed_elements": plan["elements_allowed_to_change"],
                "data_columns_used": task["columns"],
                "dependencies_used": ["matplotlib", "numpy"],
                "additional_dependencies_requested": [],
                "assumptions": ["The prepared input is a traceable derivative of verified v5 results and does not modify raw source data."],
                "warnings": plan["warnings"],
            }),
            str(task["data"]),
            final_selection_path=str(workspace / "final_template_selection.json"),
            requirement_path=str(workspace / "user_requirement.json"),
            dataset_context_path=str(workspace / "dataset_context.json"),
            catalog_path="docs/template_catalog.yaml",
            workspace_dir=str(workspace),
            outputs_dir=str(ROOT / task_name / "outputs"),
            python_executable=PYTHON,
            auto_install=False,
            timeout_seconds=120,
        )
        reports[task_name] = {
            "selection_success": selected.get("success"), "adaptation_success": adapted.get("success"),
            "selection_failure": selected.get("failed_step"), "adaptation_failure": adapted.get("failed_step"),
            "adaptation_error": adapted.get("error"),
        }
    (ROOT / "stage4_stage5_summary.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
