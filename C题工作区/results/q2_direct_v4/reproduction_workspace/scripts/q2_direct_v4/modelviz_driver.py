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

WORK = Path(__file__).resolve().parents[2]
SKILL = Path('/Users/justingao/.codex/skills/modelviz-skill')
ROOT = WORK / 'reports/q2_direct_v4/figures'
os.environ['TMPDIR'] = str(WORK / 'results/q2_direct_v4/runtime/plotting')
os.environ['MPLCONFIGDIR'] = str(WORK / 'results/q2_direct_v4/runtime/plotting/matplotlib')
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
    code = (WORK/'scripts/q2_direct_v4/plots'/f'{name}.py').read_text()
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
