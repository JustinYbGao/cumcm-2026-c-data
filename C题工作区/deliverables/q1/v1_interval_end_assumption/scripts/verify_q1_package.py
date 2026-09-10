"""Verify this frozen package and reproduce its objectives without replacing saved results."""
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True


def main():
    manifest=json.loads((ROOT/'manifest_sha256.json').read_text())
    for name,expected in manifest.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    from validate_q1_solution import validate_frames
    from solve_q1 import solve_model
    source=pd.read_csv(ROOT/'data/processed/q1_day.csv',float_precision='round_trip')
    for name in ['baseline','roundtrip_90','baseline_lp','roundtrip_90_lp','no_storage','alternate']:
        folder=ROOT/'results/q1'/name
        cfg=json.loads((folder/'config_snapshot.json').read_text())
        summary=json.loads((folder/'summary.json').read_text())
        frame=pd.read_csv(folder/'schedule.csv',float_precision='round_trip')
        assert validate_frames(source,frame,summary,cfg,relaxed=name.endswith('_lp'))['passed'],name
        if name in ['baseline','roundtrip_90']:
            for relaxed in [False,True]:
                _,status=solve_model(source,cfg,relaxed=relaxed)
                assert abs(status['objective_yuan']-summary['cost_yuan'])<1e-6
        print(name,'PASS',summary['cost_yuan'])
    print('Package hashes and numerical reproduction PASS:',len(manifest),'files')


if __name__=='__main__': main()
