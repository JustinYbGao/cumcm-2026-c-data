"""Run ModelViz stages 1 and 3 for the two updated paper figures."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from src.services.candidate_matching_pipeline import run_candidate_matching_pipeline
from src.services.requirement_parser import parse_and_save_requirement


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "reports" / "figures" / "paper_visuals_v3_v5"

TASKS = {
    "q3_policy_costs": {
        "request": (
            "Create an English, paper-ready stacked bar chart from the verified v5 results. "
            "Compare contract cost and emergency cost across four Problem 3 rolling-update "
            "policies. Highlight, but do not overstate, the selected raw-PV policy. Use a "
            "clean scientific style, muted colours, readable units, no 3D, no pie chart and "
            "no significance stars."
        ),
        "parsed": {
            "goal": "Compare the cost composition of four Problem 3 rolling-update policies.",
            "functional_keywords": ["堆叠条形图", "成本构成", "分组比较"],
            "chart_types": ["stacked_bar_chart"],
            "style_keywords": ["科研风", "简洁", "低饱和"],
            "use_case": "论文正文",
            "negative_requirements": ["三维", "饼图", "显著性标记"],
            "explicit_template": False,
            "is_ambiguous": False,
            "clarification_question": "",
        },
    },
    "q4_price_effect": {
        "request": (
            "Create an English, paper-ready dual-axis bar-and-line time-series chart from "
            "the verified v5 monthly paired comparisons. Show monthly realized savings and "
            "cumulative savings for the Q4-2 and Q4-3 OLS-versus-fixed planning-price "
            "comparisons. Positive saving means the OLS candidate is cheaper. Use a clean "
            "scientific style, muted colours, readable units, no 3D and no pie chart."
        ),
        "parsed": {
            "goal": "Compare monthly and cumulative realized savings for two Q4 price-planning comparisons.",
            "functional_keywords": ["柱状折线图", "时间序列", "成本比较"],
            "chart_types": ["dual_axis_bar_line_chart"],
            "style_keywords": ["科研风", "简洁", "低饱和"],
            "use_case": "论文正文",
            "negative_requirements": ["三维", "饼图"],
            "explicit_template": False,
            "is_ambiguous": False,
            "clarification_question": "",
        },
    },
}


def main() -> None:
    log = {}
    for task_name, task in TASKS.items():
        workspace = ROOT / task_name / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        requirement = parse_and_save_requirement(
            task["request"],
            RunnableLambda(lambda _: task["parsed"]),
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
