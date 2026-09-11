"""Copy frozen function bodies without importing modules that write old runtime paths."""
import ast
import hashlib
import json
from pathlib import Path

WORK=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
parts=['"""Frozen function bodies; source provenance in extracted_sources.json."""',
       'import highspy\nimport numpy as np\nimport pandas as pd']
records={}
for name,functions in {
    'scripts/run_q2.py':['fourier','forecast_day','execute_interval'],
    'scripts/run_q3.py':['contract_fee','solve_horizon'],
    'scripts/run_q4.py':['forecast_price'],
    'scripts/solve_q1.py':['solve_model'],
}.items():
    source=(WORK/name).read_text()
    records[name]=hashlib.sha256(source.encode()).hexdigest()
    for node in ast.parse(source).body:
        if isinstance(node,ast.FunctionDef) and node.name in functions:
            body=ast.get_source_segment(source,node)
            if node.name=='solve_model':
                body=body.replace('def solve_model(', 'def solve_target_model(').replace("e[n] == b['initial_energy_kwh']", "e[n] == b['terminal_target_kwh']")
            parts.append(body)
(HERE/'compat.py').write_text('\n\n'.join(parts)+'\n')
for name in ['kernel.c','kernel.py']:
    source=(WORK/'scripts/q2_direct_v4'/name).read_text()
    (HERE/name).write_text(source.replace('results/q2_direct_v4/runtime','results/unified_direct_v5/runtime'))
    records['scripts/q2_direct_v4/'+name]=hashlib.sha256(source.encode()).hexdigest()
(WORK/'reports/unified_direct_v5/extracted_sources.json').write_text(json.dumps(records,indent=2)+'\n')
