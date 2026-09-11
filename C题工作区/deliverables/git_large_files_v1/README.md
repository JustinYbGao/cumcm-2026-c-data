# Large review archives

Four review ZIPs exceed the regular Git single-file limit. Their original bytes
are stored here in parts of at most 64 MiB. `manifest.json` records every part's
SHA256 and the original archive's SHA256. All source code, data, results, figures
and reports are also retained in their normal project directories.

From the repository root, run Python 3.11 or later:

```bash
python3 C题工作区/deliverables/git_large_files_v1/restore.py
```

The script verifies the parts, reconstructs each ZIP at its original relative
path under `C题工作区`, and verifies the complete archive. An existing ZIP is
verified and left untouched; a mismatching file causes an error. No Git LFS is
required. Archive hashes and the original scientific package manifests remain
unchanged.
