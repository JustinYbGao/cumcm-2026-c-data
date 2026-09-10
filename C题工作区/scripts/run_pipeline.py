"""One-command rebuild; every executed analysis is a saved script in this workspace."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys

WORK = Path(__file__).resolve().parents[1]


def hashes():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((WORK/'data/processed').glob('*.csv'))}


def main():
    env = os.environ.copy()
    env['TMPDIR'] = str(WORK/'data/interim')
    env['MPLCONFIGDIR'] = str(WORK/'data/interim/matplotlib')
    before = hashes()
    steps = [('inspect_data',[]),('prepare_data',['--stage','q1']),('validate_data',['--stage','q1']),
             ('prepare_data',[]),('validate_data',[]),('diagnose_forecasts',[]),
             ('validate_forecast_diagnostics',[]),('audit_111',[]),('report_data',[])]
    results = []
    for script,args in steps:
        name = script+('_q1' if args else '')
        start = datetime.now(timezone.utc).isoformat()
        print(f'Running {name}',flush=True)
        validation_input = hashes() if script.startswith('validate_') else None
        with (WORK/f'logs/{name}.log').open('w') as log:
            completed = subprocess.run([sys.executable,str(WORK/f'scripts/{script}.py'),*args],
                                       cwd=WORK.parent,env=env,stdout=log,stderr=subprocess.STDOUT)
        results.append({'step':name,'started_utc':start,'exit_code':completed.returncode})
        if completed.returncode:
            (WORK/'logs/run_summary.json').write_text(json.dumps(results,indent=2))
            raise SystemExit(f'{name} failed; see logs/{name}.log')
        if validation_input is not None and hashes()!=validation_input:
            raise SystemExit('Validation modified a processed output; reject run')
    after = hashes()
    summary = {'steps':results,'processed_sha256':after,
               'same_as_preexisting_outputs':before==after,
               'validation_did_not_modify_outputs':True}
    (WORK/'logs/run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Completed all steps. Outputs unchanged from previous generation:',before==after)


if __name__=='__main__':
    main()
