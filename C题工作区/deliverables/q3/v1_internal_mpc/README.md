# Q3 frozen internal MPC results

Entry: papers/q3_draft.md; full A/B tables: reports/q3_representative_tables.md.
Primary six policies: results/q3. Retrospective state-feedback-only control:
results/q3_feedback_control. The control isolates feedback from PV refresh.

This is NOT a formal submission. Template time mapping, refund versus no-refund,
final-volume versus per-revision billing, efficiency and terminal-state assumptions
remain explicit unresolved interpretations. Q4 has not been run.

Numerical audits are portable: create a Python 3.12 environment, install
requirements-q3.txt, then run from this directory:

    python -B scripts/validate_q3.py
    python -B scripts/validate_q3.py --results results/q3_feedback_control
    python -B scripts/audit_q3_lp.py
    python -B -m unittest discover -s tests -p test_q3.py

Audit outputs were regenerated here before the manifest was created. Later audit
runs can change diagnostic runtime metadata, so preserve this frozen directory
and work on a copy. Core planners refuse to overwrite completed result folders.
Full recomputation requires a fresh result directory in a copied work area; the
needed cleaned inputs, inherited Q2 load predictions and core code are included.

Both figures contain English labels only and include 300-dpi PNG and SVG. Their
standalone workspace/adapted_plot.py accepts data.csv and an output directory,
without the ModelViz skill. Re-running the full ModelViz service pipeline requires
the locally installed skill; original absolute paths in provenance are historical.
Initial failed visual/schema records are retained as repair evidence; the final
quality reports and inspected image hashes identify the accepted renderings.

manifest.json contains SHA-256 values for all packaged files except itself.
The sibling ZIP and .zip.sha256 provide transport integrity. No unrelated member
workspace, original raw attachment, previous frozen package or external credential
is included. BZD dictionary attribution and complete licensing remain in query logs.
