# v5 Git delivery

After the research package was accepted, the user explicitly requested `push`.
This later instruction authorizes this commit and push; the frozen research
reports accurately retain the earlier no-commit/no-push execution boundary.

Scope: the five `unified_direct_v5` directories, this delivery log, and one
`.gitignore` entry for the local external Node dependency link. The pre-existing
untracked `papers/outline_20260911` inputs are not part of this commit.

The frozen package manifest and every listed file are preserved byte for byte.
Six already-manifested bytecode/macOS metadata files are explicitly included as
snapshot evidence despite ordinary cache ignores; this prevents a clone from
silently missing entries in the frozen SHA manifest. The external `node_modules`
symlink is not published; its dependency location is already disclosed in the
package manifest and workbook report.

No file in this delivery exceeds the repository's existing 64 MiB part size, so
no archive splitting or LFS is needed. `preflight.json` records fresh hash and
acceptance checks, and `tests_before_push.log` records the adapter test run.

The frozen CSV exports use CRLF line endings. The default Git whitespace check
reports the CR characters as trailing whitespace; a second check explicitly
accepts CR at end of line while retaining the normal whitespace checks. The
CSV bytes are not normalized because that would invalidate their frozen SHA.
