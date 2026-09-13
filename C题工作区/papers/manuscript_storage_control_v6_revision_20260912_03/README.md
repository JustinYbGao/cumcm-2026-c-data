# English manuscript revision 03

This revision applies the requested English title and refines selected body paragraphs while preserving the abstract and keywords exactly. The frozen predecessor is the sibling `manuscript_storage_control_v6_revision_20260912_02` directory.

## Deliverables

- `manuscript.pdf`: reviewed paper, identical to `outputs/manuscript_review.pdf`.
- `manuscript_EN.md`: editable English manuscript.
- `outputs/latex_source.zip`: portable typesetting source; actual extraction and compilation reproduced the reviewed PDF byte for byte.
- `support_materials.zip`: unchanged scientific support package, with its editable counterpart in `support_materials/`. It contains the scientific programs, configuration, saved evidence, five English workbooks and AI disclosure. It contains no manuscript PDF.
- `change_log.md`, `issue_resolution.csv`, `coverage.json`, `page_review.csv`, and `reports/`: private revision and verification records. These are not additional contest deliverables.

The PDF has 76 pages: abstract on page 1, body on pages 2-25 (24 pages), references on page 26, and appendices on pages 27-76. It contains 11 figures, 37 tables and 11 numbered equations. A4 dimensions, continuous footers and the revised page breaks were checked. This editorial turn did not repeat the full contest checklist or resolve submission-route requirements.

## Compile

Run from this directory with Python 3 and Pandoc available. The retained `tools/tectonic` executable and `tools/tex-cache/` provide the tested local TeX environment.

```sh
python3 code/build_pdf.py
python3 code/package_latex.py
```

The builder writes `outputs/manuscript_review.pdf`. After any new edits, review that output before replacing the delivered `manuscript.pdf`. The included Tectonic executable is for the recorded local platform. Other systems require a compatible TeX installation, fonts and packages.

## Verify or reproduce

`checks/verify_revision.py` requires `pypdf` and `pypdfium2`, plus the frozen predecessor and earlier audit paths named in the script. It compares abstract, tables, math, support identities, PDF structure and source changes and renders all pages. These are private workspace checks, not portable scientific dependencies.

```sh
python3 checks/verify_revision.py
```

`checks/check_portable_source.py` records the extracted-source compilation. It deliberately refuses an existing `checks/portable_source` directory; preserve that directory and use a new extraction location for another run. `checks/revise_body.py` records the one-time edit recipe and must not be reapplied to the already revised source.

For scientific dependencies, original-input placement and bounded runtime commands, follow `support_materials/README.md` in a fresh extracted support directory. `check_saved.py` rechecks saved results; `smoke_test.py` performs bounded diagnostics. Neither is an annual optimization. Neither was rerun in this editorial turn: the package was preserved and compared byte for byte. The annual reproduction commands are explicitly separated in that README and were not executed here.

## Scope and limits

The title and selected prose changed; detailed verification counts moved to Appendix A. Abstract, keywords, scientific functions, parameters, strategy selection, cash definitions, equations, tables, figures, workbooks and AI declaration remain unchanged. Two page-break protections were added to the typesetting converter. Scientific preservation is supported by source comparisons, exact file identities and semantic review; it is not a new proof of the underlying research conclusions.

The style reference score in `reports/style_score_recheck.json` is an editorial judgment under the previous rubric. It is not a measured AI-generated percentage or a guarantee about any external detector. Actual submission route, team verification evidence and other previously outstanding contest requirements are outside this revision.
