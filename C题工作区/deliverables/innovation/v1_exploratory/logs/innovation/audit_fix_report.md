# Innovation validator review fixes

The validator now links every saved gate hold/update candidate to independently checked evidence: exact slot keys, the retained current version's load/PV/q0, the actual ledger SOC at issue time, and the ledger's midnight day target. Candidate physics and actual replay are rebuilt from those linked values.

Risk provenance checks now require each target's availability to equal the following midnight, each model feature vector and realized target to match the independently rebuilt current target, and the latest training availability to match the causal window. Full-rank pinball models retain an independent SciPy LP objective check; empirical fallbacks additionally require rank/sample eligibility and reproduce the higher-method empirical quantile, coefficients, objective, and prediction.

Both `calibration_comparison.csv` and evaluation `comparison.csv`, plus every per-policy `innovation_summary.json`, are reconciled against verified ledgers. Checks cover policy/group/rule identity, complete 59-day February–March or 275-day evaluation scope, all exported energy and cost totals, initial/final SOC, inventory adjustment, emergency counts, gate decision/acceptance counts, and accepted changed volume. March selection remains independently calculated from March 1–31 only.

The report-generator wording now explicitly says that all 31 March days determine selection.

Final command: `TMPDIR="$PWD/data/interim/innovation" TMP="$PWD/data/interim/innovation" TEMP="$PWD/data/interim/innovation" .venv/bin/python -B scripts/validate_innovation.py > logs/innovation/validate.log 2>&1`. Result: exit code 0, 308,491 checks passed, no failed checks, and maximum recorded residual `5.85168891120702e-09`.
