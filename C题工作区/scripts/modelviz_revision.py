"""Run ModelViz services with explicitly recorded assistant-authored structured responses.

No model API call or automatic visual approval is made. Visual assessments must be
supplied after viewing the generated PNG and are tied to its SHA-256.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

WORK = Path(__file__).resolve().parents[1]
SKILL = Path('/Users/justingao/.codex/skills/modelviz-skill')
ROOT = WORK / 'reports/figures/modelviz_v3_en'
os.environ['TMPDIR'] = str(WORK / 'data/interim/modelviz_v3_en')
os.environ['MPLCONFIGDIR'] = str(WORK / 'data/interim/modelviz_v3_en/matplotlib')
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
Path(os.environ['TMPDIR']).mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL))
import pandas as pd
import yaml
from langchain_core.runnables import RunnableLambda
from src.services.requirement_parser import parse_and_save_requirement
from src.services.candidate_matching_pipeline import run_candidate_matching_pipeline
from src.services.final_template_selection_pipeline import run_final_template_selection_pipeline
from src.services.template_adaptation_pipeline import run_template_adaptation_pipeline
from src.services.plot_quality_pipeline import run_plot_quality_pipeline
from src.tools.check_python_dependencies import check_python_dependencies

SPECS = {
    'battery_states': ('q1', '比较两种效率口径下储能容量的日内时间序列与差值，说明敏感性'),
    'dispatch': ('q1', '展示储能调度的容量功率时间序列，并联读负荷、光伏、计划购电与电价'),
    'monthly_costs': ('q2', '比较月度购电费用时间序列、费用组成与两策略差值'),
    'representative_execution': ('q2', '比较四个指定日计划与实际储能容量时间序列，并显示紧急购电发生时间'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def response(obj):
    return RunnableLambda(lambda _: obj)


def checked(result):
    if isinstance(result, dict) and result.get('success') is False:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, default=str))
    return result


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    files = [p for group in ('results/q1', 'results/q2', 'data/processed')
             for p in (WORK/group).rglob('*') if p.is_file()]
    files += list((WORK/'deliverables/q1').glob('*.zip*'))
    save(ROOT/'source_hashes_before.json', {str(p.relative_to(WORK)): sha(p) for p in files})
    q1 = WORK/'results/q1'
    base = pd.read_csv(q1/'baseline/states.csv', float_precision='round_trip')
    sens = pd.read_csv(q1/'roundtrip_90/states.csv', float_precision='round_trip')
    assert base.minute.equals(sens.minute) and len(base) == 145
    states = base.rename(columns={'energy_kwh': 'baseline_energy_kwh'})
    states['roundtrip_energy_kwh'] = sens.energy_kwh
    sources = {
        'battery_states': [q1/'baseline/states.csv', q1/'roundtrip_90/states.csv'],
        'dispatch': [q1/'baseline/schedule.csv'],
        'monthly_costs': [WORK/'results/q2/monthly_comparison.csv'],
        'representative_execution': [WORK/'results/q2/selected/ledger.csv'],
    }
    frames = {'battery_states': states}
    for name in ('dispatch', 'monthly_costs', 'representative_execution'):
        frames[name] = pd.read_csv(sources[name][0], float_precision='round_trip')
    dates = ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    frames['representative_execution'] = frames['representative_execution'].loc[
        frames['representative_execution'].date.isin(dates)].copy()
    assert len(frames['representative_execution']) == 576
    for name, (_, goal) in SPECS.items():
        task = ROOT/name
        ws = task/'workspace'
        ws.mkdir(parents=True, exist_ok=True)
        (task/'docs').mkdir(exist_ok=True)
        shutil.copy2(SKILL/'docs/package_name_mapping.yaml', task/'docs/package_name_mapping.yaml')
        frames[name].to_csv(task/'data.csv', index=False)
        save(ws/'data_lineage.json', {
            'source_files': {str(p.relative_to(WORK)): sha(p) for p in sources[name]},
            'plot_data_sha256': sha(task/'data.csv'), 'rows': len(frames[name]),
            'transformation': 'Align 145 states on existing minute keys' if name=='battery_states' else
                'Select four explicitly requested dates; preserve original row order' if name=='representative_execution' else
                'Read and write plotting copy with round-trip float parsing; no reordering',
            'display_units': 'kWh / 1000 = MWh; kW / 1000 = MW; yuan / 10000 = 万元',
            'time_assumption': 'Internal interval-end assumption; no data shifting; not formal submission',
        })
        requirement = dict(original_request='不要中文标注！！全部要英文的',
            goal=goal, functional_keywords=(['趋势','比较','复合时间序列','多指标时间序列']
                if name in ('battery_states','monthly_costs') else ['趋势','比较','时间序列','容量功率','多面板']),
            chart_types=[], style_keywords=['English labels','serif typography'], use_case='论文正文',
            negative_requirements=['No Chinese text in figures'], explicit_template=False, is_ambiguous=False, clarification_question='')
        parse_and_save_requirement(requirement['original_request'], response(requirement),
            vocabulary_path=SKILL/'docs/requirement_vocabulary.yaml', output_path=ws/'user_requirement.json')
        checked(run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),
            catalog_path=str(SKILL/'docs/template_catalog.yaml'), output_path=str(ws/'candidate_templates.json'),
            top_k=8, min_score=.1))
        save(ws/'response_provenance.json', {'author': 'Codex current assistant',
             'method': 'Assistant-authored structured outputs passed through RunnableLambda; no external model API',
             'visual_check': 'Pending actual image inspection; never inferred from script success'})
        print(name, (ws/'candidate_templates.json').read_text())


def adapt(name):
    task = ROOT/name
    ws = task/'workspace'
    os.chdir(task)
    decisions = json.loads((ws/'assistant_decisions.json').read_text())
    checked(run_final_template_selection_pipeline(model=response(decisions['selection']),
        data_path=str(task/'data.csv'), requirement_path=str(ws/'user_requirement.json'),
        candidate_path=str(ws/'candidate_templates.json'), output_path=str(ws/'final_template_selection.json'),
        dataset_context_path=str(ws/'dataset_context.json')))
    # Absolute-path catalog snapshot avoids modifying the read-only skill or relying on cwd.
    catalog = yaml.safe_load((SKILL/'docs/template_catalog.yaml').read_text())
    # The bundled pipeline validates dependencies_used before its extra-dependency
    # pass. Check the adapter's CSV/array dependencies first and merge them only
    # into this task's catalog copy, retaining the original source hash.
    checked(check_python_dependencies.invoke({'dependencies':['numpy','pandas','matplotlib'],
        'output_path':str(ws/'adapter_dependency_preflight.json')}))
    for item in catalog['templates']:
        for key in ('code_path','preview'):
            item[key] = str(SKILL/item[key])
        if item['id']==decisions['selection']['selected_template_id']:
            save(ws/'template_provenance.json', {'source_catalog_sha256':sha(SKILL/'docs/template_catalog.yaml'),
                'source_script':item['code_path'],'source_script_sha256':sha(item['code_path']),
                'source_preview':item['preview'],'source_preview_sha256':sha(item['preview']),
                'original_dependencies':item['dependencies'],
                'local_catalog_additions':['numpy','pandas'],
                'reason':'Adapter dependency preflight; bundled service validates before extra-dependency pass. Original catalog/template are unchanged.'})
            item['dependencies']=list(dict.fromkeys(item['dependencies']+['numpy','pandas']))
    (task/'docs/template_catalog.yaml').write_text(yaml.safe_dump(catalog, allow_unicode=True))
    code = (WORK/'scripts/modelviz'/f'{name}.py').read_text()
    result = checked(run_template_adaptation_pipeline(plan_model=response(decisions['plan']),
        code_model=response(dict(adapted_code=code, **decisions['adaptation'])),
        data_path=str(task/'data.csv'), final_selection_path=str(ws/'final_template_selection.json'),
        requirement_path=str(ws/'user_requirement.json'), dataset_context_path=str(ws/'dataset_context.json'),
        catalog_path=str(task/'docs/template_catalog.yaml'), workspace_dir=str(ws),
        outputs_dir=str(task/'outputs'), auto_install=False))
    save(ws/'adaptation_execution.json', result)
    print(name, 'rendered')


def quality(name):
    task = ROOT/name
    ws = task/'workspace'
    os.chdir(task)
    assessment = json.loads((ws/'assistant_visual_assessment.json').read_text())
    assert sha(task/'outputs/chart.png') == assessment['inspected_png_sha256']
    assert sha(ws/'adapted_plot.py') == assessment['inspected_script_sha256']
    result = checked(run_plot_quality_pipeline(visual_model=response(assessment['report']),
        repair_model=None, script_path=str(ws/'adapted_plot.py'), data_path=str(task/'data.csv'),
        output_directory=str(task/'outputs'), max_repair_attempts=0))
    save(ws/'quality_execution.json', result)
    print(name, 'quality passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare','adapt','quality'])
    parser.add_argument('--figure', choices=list(SPECS))
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare()
    else:
        for name in ([args.figure] if args.figure else SPECS):
            {'adapt': adapt, 'quality': quality}[args.stage](name)
