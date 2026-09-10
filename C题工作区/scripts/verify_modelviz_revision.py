"""Independent checks of plot inputs, numerical summaries, provenance and linked artifacts."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
from PIL import Image

WORK=Path(__file__).resolve().parents[1]
ROOT=WORK/'reports/figures/modelviz_v3_en'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def frame(path): return pd.read_csv(path,float_precision='round_trip')


def main():
    checks=[]
    def check(name,condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition: raise AssertionError(name)
    before=read(ROOT/'source_hashes_before.json')
    for rel,expected in before.items():check('unchanged: '+rel,sha(WORK/rel)==expected)
    dimensions={}
    for name in ['battery_states','dispatch','monthly_costs','representative_execution']:
        task=ROOT/name;ws=task/'workspace'
        lineage=read(ws/'data_lineage.json');review=read(ws/'assistant_visual_assessment.json')
        check(name+': plotting data hash',sha(task/'data.csv')==lineage['plot_data_sha256'])
        check(name+': reviewed image hash',sha(task/'outputs/chart.png')==review['inspected_png_sha256'])
        check(name+': reviewed script hash',sha(ws/'adapted_plot.py')==review['inspected_script_sha256'])
        check(name+': source code equals executed adapter',sha(WORK/'scripts/modelviz'/f'{name}.py')==sha(ws/'adapted_plot.py'))
        technical=read(ws/'technical_quality_report.json')
        check(name+': technical and visual pass',technical['passed'] and not technical['issues'] and not technical['warnings'] and read(ws/'final_quality_report.json')['passed'] and review['report']['passed'])
        with Image.open(task/'outputs/chart.png') as image:
            image.load();dimensions[name]=list(image.size)
            check(name+': at least 300dpi',min(image.info['dpi'])>=299.9)
            check(name+': nonblank PNG',np.asarray(image).var()>100)
        check(name+': readable SVG',ET.parse(task/'outputs/chart.svg').getroot().tag.endswith('svg'))
        check(name+': no Chinese in SVG',not re.search(r'[\u3400-\u9fff]',(task/'outputs/chart.svg').read_text()))
        check(name+': no Chinese in plotting code',not re.search(r'[\u3400-\u9fff]',(ws/'adapted_plot.py').read_text()))
        choice=read(ws/'final_template_selection.json')['selected_template_id']
        check(name+': chosen from actual candidates',choice in [c['template_id'] for c in read(ws/'candidate_templates.json')['candidates']])
        provenance=read(ws/'template_provenance.json')
        check(name+': original template unchanged',sha(Path(provenance['source_script']))==provenance['source_script_sha256'])
        check(name+': original preview unchanged',sha(Path(provenance['source_preview']))==provenance['source_preview_sha256'])
    states=frame(ROOT/'battery_states/data.csv')
    for scenario,column in [('baseline','baseline_energy_kwh'),('roundtrip_90','roundtrip_energy_kwh')]:
        original=frame(WORK/f'results/q1/{scenario}/states.csv')
        check(scenario+': all 145 time keys preserved',len(states)==145 and np.array_equal(states.minute,original.minute))
        check(scenario+': all state values preserved',np.allclose(states[column],original.energy_kwh,rtol=0,atol=1e-10))
    for name,path in [('dispatch','results/q1/baseline/schedule.csv'),('monthly_costs','results/q2/monthly_comparison.csv')]:
        pd.testing.assert_frame_equal(frame(ROOT/name/'data.csv'),frame(WORK/path),check_exact=False,rtol=0,atol=1e-10)
        check(name+': every plotting input column preserved',True)
    facts=read(ROOT/'dispatch/workspace/plot_facts.json')
    check('Q1 cost unchanged',abs(facts['cost_yuan']-read(WORK/'results/q1/baseline/summary.json')['cost_yuan'])<1e-7)
    check('Q1 plot limits do not clip power',facts['maximum_power_mw']<10.6)
    monthly=frame(ROOT/'monthly_costs/data.csv')
    comparison=frame(WORK/'results/q2/comparison.csv').set_index('policy')
    check('Q2 monthly selected total equals ledger total',abs(monthly.total_cost_yuan.sum()-comparison.loc['selected','total_cost_yuan'])<1e-6)
    check('Q2 monthly seasonal total equals ledger total',abs(monthly.seasonal_total_cost_yuan.sum()-comparison.loc['seasonal','total_cost_yuan'])<1e-6)
    check('Q2 cost gap unchanged',abs(monthly.excess_cost_yuan.sum()-955476.04205744)<1e-5)
    subset=frame(ROOT/'representative_execution/data.csv')
    ledger=frame(WORK/'results/q2/selected/ledger.csv')
    original=ledger.loc[ledger.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])].reset_index(drop=True)
    pd.testing.assert_frame_equal(subset,original,check_exact=False,rtol=0,atol=1e-10)
    check('Q2 representative subset and row order preserved',len(subset)==576)
    check('Q2 emergency scale does not clip bars',subset.emergency_kwh.max()<1000)
    for rel in ['papers/q1_draft.md','reports/q1_model_and_results.md','reports/q2_model_and_results.md','reports/modelviz_v3_en_revision.md']:
        path=WORK/rel
        links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',path.read_text())
        check(rel+': images use new version',bool(links) and all('modelviz_v3_en/' in p for p in links))
        check(rel+': all image targets exist',all((path.parent/p).exists() for p in links))
    archive=WORK/'deliverables/q1/v1_interval_end_assumption.zip'
    with zipfile.ZipFile(archive) as z:check('Q1 original ZIP CRC',z.testzip() is None)
    result={'passed':True,'checks_count':len(checks),'checks':checks,'unchanged_source_files':len(before),
            'dimensions_pixels':dimensions,'note':'No optimization rerun; checks apply to plots and existing results'}
    (ROOT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
