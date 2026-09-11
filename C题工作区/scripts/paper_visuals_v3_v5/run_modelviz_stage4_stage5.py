"""Run ModelViz template selection and adaptation for the updated v5 figures.

The structured responses deliberately select only templates returned by Stage 3.
They encode an English adaptation for the compact plotting tables prepared from
the verified results bundle; no raw inputs or source templates are modified.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from src.services.final_template_selection_pipeline import run_final_template_selection_pipeline
from src.services.template_adaptation_pipeline import run_template_adaptation_pipeline


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "reports" / "figures" / "paper_visuals_v3_v5"
PYTHON = "/Users/mike/Documents/Codex/2026-09-10/zhe/work/notebook-env/bin/python3"

Q3_CODE = r'''from __future__ import annotations

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
    fig, ax = plt.subplots(figsize=(8.1, 4.8), constrained_layout=True)
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
    ax.set_ylim(0, max(total) + 0.42)
    ax.yaxis.grid(True, color="#D9D9D9", linewidth=0.65, alpha=0.9)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False, ncol=2, handlelength=1.35)
    ax.text(selected_index, -0.11, "selected policy", transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=8.8, color="#40566F")
    fig.savefig(output_dir / "chart.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "chart.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
'''

Q4_CODE = r'''from __future__ import annotations

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
'''

TASKS = {
    "q3_policy_costs": {
        "data": ROOT / "q3_policy_costs" / "data" / "q3_policy_costs.csv",
        "selection": {
            "dataset_summary": "Four verified Problem 3 policy records with contract, emergency, and total realized costs in million CNY.",
            "observed_data_features": ["Four categorical policies", "Two additive cost components", "One selected policy flag"],
            "relevant_columns": ["policy_label", "contract_cost_million_cny", "emergency_cost_million_cny", "total_cost_million_cny", "selected"],
            "candidate_comparisons": [],
            "selected_template_id": "cmp_correlation_stacked_bar",
            "selected_template_name": "相关性分析堆叠条形图",
            "alternative_template_ids": ["cmp_horizontal_percentage_stack"],
            "selection_reason": "An absolute stacked bar preserves the additive cost decomposition and enables direct policy comparison without normalising away the cost level.",
            "data_support_reason": "Contract and emergency costs are non-negative additive components available for every policy.",
            "data_warnings": ["The selected-policy flag denotes the frozen v5 choice, not statistical significance."],
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": "",
        },
        "plan": {
            "template_id": "cmp_correlation_stacked_bar",
            "template_name": "相关性分析堆叠条形图",
            "plot_goal": "Show the verified cost composition of the four Problem 3 policies in English.",
            "selected_columns": ["policy_label", "policy_order", "contract_cost_million_cny", "emergency_cost_million_cny", "total_cost_million_cny", "selected"],
            "column_mappings": [
                {"data_column": "policy_label", "template_role": "categorical x-axis", "reason": "Policy labels provide the comparison groups."},
                {"data_column": "contract_cost_million_cny", "template_role": "lower stack", "reason": "First additive cost component."},
                {"data_column": "emergency_cost_million_cny", "template_role": "upper stack", "reason": "Second additive cost component."},
                {"data_column": "total_cost_million_cny", "template_role": "total annotation", "reason": "Exact stacked totals are reported above the bars."},
                {"data_column": "selected", "template_role": "context highlight", "reason": "Identifies the frozen v5 policy without an inferential claim."},
            ],
            "required_preprocessing": ["Sort rows by policy_order; use values already converted to million CNY."],
            "required_dependencies": ["matplotlib", "numpy", "pandas"],
            "layout_elements_to_preserve": ["upright bar comparison", "stacked component layout", "compact legend"],
            "style_elements_to_preserve": ["serif scientific typography", "muted two-colour palette", "light grid"],
            "elements_allowed_to_change": ["English labels", "remove template-specific correlation semantics", "add restrained selected-policy band"],
            "title_plan": "No internal title; manuscript caption supplies the figure title.",
            "axis_plan": "Categorical policy labels and realized cost in million CNY.",
            "legend_plan": "Two component labels in the upper right.",
            "annotation_plan": "Total cost to three decimals above each bar; selected policy label below its bar.",
            "output_formats": ["png", "svg"],
            "warnings": ["No causal interpretation is encoded by the chart."],
            "can_proceed": True,
            "clarification_question": "",
        },
        "code": Q3_CODE,
        "columns": ["policy_label", "policy_order", "contract_cost_million_cny", "emergency_cost_million_cny", "total_cost_million_cny", "selected"],
        "dependencies": ["matplotlib", "numpy", "pandas"],
        "summary": ["Replaced demonstration factors with verified v5 policy-cost columns.", "Preserved the selected stacked-bar template family while using English paper labels."],
    },
    "q4_price_effect": {
        "data": ROOT / "q4_price_effect" / "data" / "q4_price_effect.csv",
        "selection": {
            "dataset_summary": "Monthly paired realized savings for two OLS-versus-fixed planning-price comparisons, with cumulative savings computed in chronological order.",
            "observed_data_features": ["Two categorical comparison branches", "Eleven monthly observations per branch", "Monthly signed savings and cumulative signed savings"],
            "relevant_columns": ["comparison_id", "comparison_label", "month", "monthly_saving_yuan", "cumulative_saving_yuan"],
            "candidate_comparisons": [],
            "selected_template_id": "trd_dual_axis_bar_line",
            "selected_template_name": "双Y轴柱状折线时间序列图",
            "alternative_template_ids": ["trd_composite_line_bar_dual_axis"],
            "selection_reason": "The dual-axis bar-and-line layout separates month-level fluctuations from the cumulative annual comparison in each Q4 branch.",
            "data_support_reason": "Both signed monthly savings and accumulated savings are present at the same monthly time scale.",
            "data_warnings": ["The two branches have different information structures; the panels are matched within branch and must not be read as an absolute cross-branch ranking."],
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": "",
        },
        "plan": {
            "template_id": "trd_dual_axis_bar_line",
            "template_name": "双Y轴柱状折线时间序列图",
            "plot_goal": "Show within-branch monthly and cumulative realized OLS-price savings for the two Q4 comparisons.",
            "selected_columns": ["comparison_id", "comparison_label", "month", "monthly_saving_yuan", "cumulative_saving_yuan"],
            "column_mappings": [
                {"data_column": "month", "template_role": "time x-axis", "reason": "All records are monthly and chronologically ordered."},
                {"data_column": "monthly_saving_yuan", "template_role": "bar series", "reason": "Shows signed month-level realized saving."},
                {"data_column": "cumulative_saving_yuan", "template_role": "line series", "reason": "Shows the cumulative annual difference."},
                {"data_column": "comparison_id", "template_role": "small-multiple grouping", "reason": "Keeps Q4-2 and Q4-3 matched comparisons separate."},
            ],
            "required_preprocessing": ["Group rows by comparison_id, sort by month, and express both monetary series in thousand CNY only for axis readability."],
            "required_dependencies": ["matplotlib", "numpy"],
            "layout_elements_to_preserve": ["dual y-axes", "bar-plus-line time-series structure", "compact legends"],
            "style_elements_to_preserve": ["serif scientific typography", "muted gradient-inspired paired colours", "inward-looking clean axes"],
            "elements_allowed_to_change": ["replace hourly power/SOC values with monthly saving data", "use two panels because the branches are not directly comparable"],
            "title_plan": "Panel titles identify the within-branch OLS vs. fixed comparison.",
            "axis_plan": "Monthly saving bars on the left axis and cumulative saving line on the right axis, both in thousand CNY.",
            "legend_plan": "One compact legend in each panel.",
            "annotation_plan": "Annotate only the final cumulative value and state the positive-saving convention in a footnote." ,
            "output_formats": ["png", "svg"],
            "warnings": ["No confidence interval or significance label is added because the visual is descriptive."],
            "can_proceed": True,
            "clarification_question": "",
        },
        "code": Q4_CODE,
        "columns": ["comparison_id", "comparison_label", "month", "monthly_saving_yuan", "cumulative_saving_yuan"],
        "dependencies": ["matplotlib", "numpy"],
        "summary": ["Replaced hourly power/SOC demonstration data with verified v5 paired monthly savings.", "Preserved the dual-axis bar-line structure while separating non-comparable Q4 branches into panels."],
    },
}


def as_runnable(value):
    return RunnableLambda(lambda _, result=value: result)


def main() -> None:
    reports = {}
    for task_name, task in TASKS.items():
        task_root = ROOT / task_name
        workspace = task_root / "workspace"
        outputs = task_root / "outputs"
        data = task["data"]
        selected = run_final_template_selection_pipeline(
            as_runnable(task["selection"]),
            str(data),
            requirement_path=str(workspace / "user_requirement.json"),
            candidate_path=str(workspace / "candidate_templates.json"),
            output_path=str(workspace / "final_template_selection.json"),
            dataset_context_path=str(workspace / "dataset_context.json"),
        )
        adapted = run_template_adaptation_pipeline(
            as_runnable(task["plan"]),
            as_runnable({
                "adapted_code": task["code"],
                "changes_summary": task["summary"],
                "preserved_style_elements": task["plan"]["style_elements_to_preserve"] + task["plan"]["layout_elements_to_preserve"],
                "changed_elements": task["plan"]["elements_allowed_to_change"],
                "data_columns_used": task["columns"],
                "dependencies_used": task["dependencies"],
                "additional_dependencies_requested": [],
                "assumptions": ["The compact plotting table is a traceable extract from the verified v5 result bundle."],
                "warnings": task["plan"]["warnings"],
            }),
            str(data),
            final_selection_path=str(workspace / "final_template_selection.json"),
            requirement_path=str(workspace / "user_requirement.json"),
            dataset_context_path=str(workspace / "dataset_context.json"),
            catalog_path="docs/template_catalog.yaml",
            workspace_dir=str(workspace),
            outputs_dir=str(outputs),
            python_executable=PYTHON,
            auto_install=False,
            timeout_seconds=120,
        )
        reports[task_name] = {
            "selection_success": selected.get("success"),
            "adaptation_success": adapted.get("success"),
            "selection_failure": selected.get("failed_step"),
            "adaptation_failure": adapted.get("failed_step"),
            "adaptation_error": adapted.get("error"),
        }
    (ROOT / "stage4_stage5_summary.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
