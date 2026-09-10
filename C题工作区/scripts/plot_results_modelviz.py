"""Re-render reviewed ModelViz adapters, refusing stale data or unreviewed images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WORK=Path(__file__).resolve().parents[1]
GROUPS={'q1':['battery_states','dispatch'],'q2':['monthly_costs','representative_execution']}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(group):
    root=WORK/'reports/figures/modelviz_v3_en'
    env=os.environ.copy()
    env.update(TMPDIR=str(WORK/'data/interim/modelviz_v3_en'),
        MPLCONFIGDIR=str(WORK/'data/interim/modelviz_v3_en/matplotlib'),PYTHONDONTWRITEBYTECODE='1')
    for name in GROUPS[group]:
        task=root/name; ws=task/'workspace'
        lineage=json.loads((ws/'data_lineage.json').read_text())
        review=json.loads((ws/'assistant_visual_assessment.json').read_text())
        for rel,expected in lineage['source_files'].items():
            if digest(WORK/rel)!=expected: raise RuntimeError(f'{name}: source changed; rerun ModelViz adaptation and visual review')
        assert digest(task/'data.csv')==lineage['plot_data_sha256']
        assert digest(ws/'adapted_plot.py')==review['inspected_script_sha256']
        assert digest(WORK/'scripts/modelviz'/f'{name}.py')==review['inspected_script_sha256']
        result=subprocess.run([sys.executable,str(ws/'adapted_plot.py'),str(task/'data.csv'),str(task/'outputs')],
            cwd=task,env=env,capture_output=True,text=True,check=True)
        (ws/'rerender.log').write_text(result.stdout+result.stderr)
        if digest(task/'outputs/chart.png')!=review['inspected_png_sha256']:
            raise RuntimeError(f'{name}: image differs from reviewed version; visual review required')
        print(f'{name}: rendered identically to reviewed PNG')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--question',choices=['q1','q2','all'],default='all')
    args=parser.parse_args()
    for group in (GROUPS if args.question=='all' else [args.question]): render(group)
