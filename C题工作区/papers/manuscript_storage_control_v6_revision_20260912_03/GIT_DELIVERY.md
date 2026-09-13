# Revision 03 repository delivery

This directory is the current English paper and scientific support delivery. The earlier sibling revisions and experimental working directories remain frozen in the original workspace; this commit publishes revision 03.

## Files to use

- `manuscript.pdf`: reviewed paper with the updated title and unchanged abstract.
- `manuscript_EN.md`: editable manuscript.
- `support_materials.zip` and `support_materials/`: identical packaged and editable scientific support, including all five workbooks, model programs, saved decisions and AI disclosure.
- `outputs/latex_source.zip`: complete portable typesetting source.
- `change_log.md`, `issue_resolution.csv`, `coverage.json`, `page_review.csv`, `checks/pages/` and `reports/`: revision evidence. These are repository records, not extra contest submission files.

Compiler executables, TeX caches, intermediate compilation history and the temporary extracted source tree are retained locally and excluded from Git. All final page images referenced by `page_review.csv` are included. Their hashes bind the recorded observations to the delivered PDF. Earlier visual attempts and predecessor files referenced by private workspace checks are not included in this revision-only repository delivery.

## Compile from a fresh checkout

The simplest route uses the complete LaTeX archive and an installed Tectonic or XeLaTeX environment:

```sh
unzip outputs/latex_source.zip -d latex_build
cd latex_build
tectonic main.tex
```

The first compilation on another host may need TeX packages and compatible fonts. `reports/portable_compile.json` records an actual extracted compilation on the original host which reproduced the delivered PDF byte for byte. It is not a guarantee of identical bytes on every host.

To regenerate typesetting fragments from the frozen Markdown source, install Pandoc 3.11 or a compatible version and run from this directory:

```sh
python3 code/convert_manuscript.py --pandoc "$(command -v pandoc)"
tectonic main.tex --outdir outputs
```

This writes a newly compiled `outputs/main.pdf`; inspect it before replacing the reviewed delivery. The local convenience script `code/build_pdf.py` expects the original `tools/` layout and is therefore not the fresh-checkout entry point. Its source is retained to document the original build.

## Scientific execution and verification

Follow `support_materials/README.md` for Python dependencies, raw attachment placement and bounded checks. The scientific package does not depend on the excluded compiler tools or earlier paper revisions. Use a fresh extracted support copy for any run. Annual reproduction is optional and explicitly separated in that README; no annual experiment was executed for this Git publication.

`checks/verify_revision.py` and `checks/finalize_revision.py` document private workspace comparisons against frozen predecessor and audit directories. They are not standalone fresh-checkout checks. The committed reports preserve their observed results. The paper, support ZIP, portable source ZIP and source hashes are listed in `reports/final_delivery.json`.

The recorded style score is a subjective editorial reference and not a measured AI-generated percentage. This Git publication does not resolve outstanding submission-route or team-evidence requirements.
