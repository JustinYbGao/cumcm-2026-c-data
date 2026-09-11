# Paper Visuals v2 — Data Preparation

This package contains the two English-only figures inserted into the manuscript's common-data-processing subsection.

| Paper figure | Asset directory | Evidence represented |
|---|---|---|
| Figure 2 | `data_pipeline/outputs` | The declared parsing, unit conversion, structural-label handling, audit, and cross-problem data interface. |
| Figure 3 | `data_coverage/outputs` | Retained record coverage and the monthly count of valid zero and positive actual-PV observations. |

The renderer is `scripts/paper_visuals_v2_preprocessing/render.py`. It takes immutable processed data and existing validation records as input, copies those inputs to `data/`, records their SHA-256 hashes in `plot_facts.json`, and writes 300 dpi PNG plus SVG outputs. It does not alter raw workbooks, processed inputs, result workbooks, templates, or frozen model artifacts.

The project instruction requests `/Users/justingao/.codex/skills/modelviz-skill/SKILL.md`; that path is unavailable on this host. This package therefore applies the existing project scientific-figure conventions and records the limitation rather than claiming a ModelViz template-selection run. The completed visual and technical checks are recorded in `QUALITY_CHECK.md`.

Figure 3 distinguishes valid zero PV from missing PV. The 1,095 blank date labels in Attachment 3 are repeated structural labels, not 1,095 missing forecast values. The first forecast release lacks a prior endpoint for its first hour; the processing pipeline leaves those six ten-minute forecast intervals unavailable rather than manufacturing a value.
