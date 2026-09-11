"""Run ModelViz requirement parsing and candidate recall for explanatory charts."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from src.services.candidate_matching_pipeline import run_candidate_matching_pipeline
from src.services.requirement_parser import parse_and_save_requirement


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "reports" / "figures" / "paper_visuals_v4_explanation"

TASKS = {
    "q3_monthly_saving": {
        "request": (
            "Create an English, paper-ready time-series chart from verified Problem 3 monthly "
            "savings. Show monthly and cumulative realized savings of the selected raw-PV rolling "
            "policy relative to the no-update policy. Use a clean scientific style, muted colours, "
            "readable units, no 3D, no pie chart, no smoothing, and no significance stars."
        ),
        "parsed": {
            "goal": "Show how the realized saving of the selected Problem 3 update policy accumulates over months.",
            "functional_keywords": ["柱状折线图", "时间序列", "累计节省"],
            "chart_types": ["dual_axis_bar_line_chart"],
            "style_keywords": ["科研风", "简洁", "低饱和"],
            "use_case": "论文正文",
            "negative_requirements": ["三维", "饼图", "平滑曲线", "显著性标记"],
            "explicit_template": False,
            "is_ambiguous": False,
            "clarification_question": "",
        },
    },
    "q3_peak_day_execution": {
        "request": (
            "Create an English, paper-ready two-panel time-series chart from a verified Problem 3 "
            "selected-policy daily ledger. Explain the physical executor on the single day with the "
            "largest realized emergency purchase: net load, regular grid purchase, emergency purchase, "
            "battery net energy, and state of charge. Use stepwise raw scheduling points only, muted "
            "scientific colours, readable units, no 3D, no pie chart, no smoothing, and no significance stars."
        ),
        "parsed": {
            "goal": "Explain the selected Problem 3 policy's interval-by-interval physical execution on a traceably chosen stress day.",
            "functional_keywords": ["时间序列", "双Y轴", "调度轨迹"],
            "chart_types": ["composite_time_series_chart"],
            "style_keywords": ["科研风", "简洁", "低饱和"],
            "use_case": "论文正文",
            "negative_requirements": ["三维", "饼图", "平滑曲线", "显著性标记"],
            "explicit_template": False,
            "is_ambiguous": False,
            "clarification_question": "",
        },
    },
    "q43_causal_trace": {
        "request": (
            "Create an English, paper-ready two-panel time-series chart from a verified Problem 4-3 "
            "causal-audit day. Show actual electricity price and the four available price-forecast "
            "versions above, and show the associated grid-purchase plan versions plus the executed "
            "purchase below. Use stepwise raw scheduling points only, a clean muted scientific style, "
            "readable units, no 3D, no pie chart, no smoothing, and no significance stars."
        ),
        "parsed": {
            "goal": "Explain the causal price-information and rolling-plan boundary in the selected Problem 4-3 policy.",
            "functional_keywords": ["时间序列", "多线图", "调度轨迹"],
            "chart_types": ["composite_time_series_chart"],
            "style_keywords": ["科研风", "简洁", "低饱和"],
            "use_case": "论文正文",
            "negative_requirements": ["三维", "饼图", "平滑曲线", "显著性标记"],
            "explicit_template": False,
            "is_ambiguous": False,
            "clarification_question": "",
        },
    },
}


def main() -> None:
    log: dict[str, object] = {}
    for task_name, task in TASKS.items():
        workspace = ROOT / task_name / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        requirement = parse_and_save_requirement(
            task["request"],
            RunnableLambda(lambda _, payload=task["parsed"]: payload),
            vocabulary_path="docs/requirement_vocabulary.yaml",
            output_path=workspace / "user_requirement.json",
        )
        candidates = run_candidate_matching_pipeline(
            requirement_path=str(workspace / "user_requirement.json"),
            catalog_path="docs/template_catalog.yaml",
            output_path=str(workspace / "candidate_templates.json"),
            top_k=8,
            min_score=0.10,
        )
        log[task_name] = {
            "requirement": requirement.model_dump(),
            "candidate_success": candidates.get("success"),
            "candidate_ids": [
                item.get("template_id")
                for item in candidates.get("candidate_result", {}).get("candidates", [])
            ],
        }
    (ROOT / "stage3_summary.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
