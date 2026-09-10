"""Reconcile friend's outputs and rerun reviewed notebook code without exports."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
ROOT = WORK.parent
os.environ['MPLCONFIGDIR'] = str(WORK/'data/interim/matplotlib')
import matplotlib
matplotlib.use('Agg')


def main():
    friend = ROOT/'111'
    snapshots = {str(p.relative_to(friend)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in friend.rglob('*') if p.is_file() and p.name!='.DS_Store'}
    evidence, lines = [], ['# 111 工作审计', '', '只读检查原目录；在本工作区运行经过审阅的笔记本代码副本，关闭导出。下述缺项是111原交付的进度记录；C题工作区已补齐的内容见data_completion.md。', '']
    for p in sorted((friend/'附件').rglob('*.xlsx')):
        if p.name.startswith('~$'):
            continue
        original = ROOT/'CUMCM2026Problems/C题/附件'/p.relative_to(friend/'附件')
        same = p.read_bytes()==original.read_bytes()
        evidence.append({'type':'source_hash','file':str(p.relative_to(friend)),'equal':same})
    source = (WORK/'data/interim/C题-数据处理-已运行.py').read_text()
    # Only environment and side-effect changes. Transformation logic is unchanged.
    adapted = source.replace('%matplotlib inline', '')
    adapted = adapted.replace('ROOT = Path.cwd()', f'ROOT = Path({str(friend)!r})')
    adapted = adapted.replace('EXPORT = True','EXPORT = False')
    adapted = adapted.replace('plt.show()', 'plt.close(fig)')
    run_file = WORK/'data/interim/friend_notebook_rerun.py'
    run_file.write_text(adapted)
    namespace = {'__name__':'friend_audit'}
    with (WORK/'logs/friend_notebook_rerun.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        exec(compile(adapted,str(run_file),'exec'),namespace)
    output_dirs = sorted(p for p in (friend/'处理结果').iterdir() if p.is_dir())
    for output_dir in output_dirs:
        for name in ['q1_day','fixed_price','actual_10min','pv_forecast_hourly']:
            path = output_dir/f'{name}.csv'
            if not path.exists():
                evidence.append({'type':'missing','file':str(path),'equal':False})
                continue
            old = pd.read_csv(path,float_precision='round_trip')
            new = pd.read_csv(WORK/'data/processed'/f'{name}.csv',float_precision='round_trip')
            rerun = namespace[name].copy()
            keys = ['slot_id'] if name in ['q1_day','fixed_price'] else (['interval_start'] if name=='actual_10min' else ['issue_time','target_time'])
            def normalize(df):
                df = df.copy()
                for c in ['date','interval_start','interval_end','issue_time','target_time']:
                    if c in df:
                        df[c] = pd.to_datetime(df[c])
                for c in ['start_time','end_time']:
                    if c in df:
                        df[c] = df[c].astype(str).str.slice(0,5)
                return df.sort_values(keys).reset_index(drop=True)
            old,new,rerun = map(normalize,[old,new,rerun])
            result = {'type':'table','file':str(path.relative_to(ROOT)),'rows':len(old),'columns':{},'rerun_equal':True}
            for col in old:
                if col not in new:
                    result['columns'][col] = False
                elif pd.api.types.is_numeric_dtype(old[col]):
                    result['columns'][col] = bool(np.allclose(old[col],new[col],rtol=1e-13,atol=1e-10))
                else:
                    result['columns'][col] = bool(old[col].equals(new[col]))
                if pd.api.types.is_numeric_dtype(old[col]):
                    result['rerun_equal'] &= bool(np.allclose(old[col],rerun[col],rtol=1e-13,atol=1e-10))
                else:
                    result['rerun_equal'] &= bool(old[col].equals(rerun[col]))
            result['equal'] = all(result['columns'].values()) and result['rerun_equal'] and len(old)==len(new) and not old.duplicated(keys).any()
            evidence.append(result)
            lines.append(f'- `{path.relative_to(ROOT)}`：{len(old)} 行，原有全部字段与独立重建表逐列核对：{"通过" if result["equal"] else "未通过，见 JSON"}；笔记本重跑一致：{result["rerun_equal"]}。')
    unchanged = all(hashlib.sha256((friend/p).read_bytes()).hexdigest()==v for p,v in snapshots.items())
    evidence.append({'type':'friend_files_unchanged','equal':unchanged})
    source_equal = all(e['equal'] for e in evidence if e['type']=='source_hash')
    lines += ['',f'附件副本与官方目录 SHA-256 全部一致：{source_equal}。111 中所有原文件运行前后哈希一致：{unchanged}。',
              '', '## 进度判断', '',
              '已完成四张核心基础表：Q1、固定电价、全年供需与两类电价、全部小时预报版本。已有区间结束口径、功率÷6、负净负载、跨年保留和历史/预报筛选函数。当前未发现这些表的数值或时序整理错误，结论限定于采用的区间平均功率假设。',
              '', '## 尚缺内容与可复现性问题', '',
              '- 未交付 pv_forecast_10min.csv，Q3/Q4 十分钟预报接口未完成。',
              '- 未检查附件5时段标签偏移等模板问题；不能据此直接按列写正式结果。',
              '- 没有独立输出读回验证、完整数据字典、原行列与日期填充记录。',
              '- 笔记本从项目根目录启动时找不到附件，会回退到 /Users/mike/Desktop/国赛；应从111启动或修改ROOT。本次仅对代码副本调整ROOT，关闭导出，将inline绘图改为无界面关闭。',
              '- 基础图保存在已运行笔记本的输出内，已有按日汇总代码；未独立落图、未完成尖峰诊断。',
              '- history_at / forecasts_at 的比较方向正确，但只展示一个决策时刻，没有独立测试。',
              '- 未完成最终预测、优化或竞赛结果；这些不属于本轮数据任务，不算数据处理错误。',
              '', '## 可复查证据', '',
              '`111_audit.json` 为逐字段比较；`logs/friend_notebook_rerun.log` 为本次真实重跑日志；`data/interim/friend_notebook_rerun.py` 为运行副本。原笔记本与结果均未覆盖。']
    (WORK/'reports/111_audit.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    (WORK/'reports/111_audit.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
    if not all(e['equal'] for e in evidence):
        raise SystemExit('Some audit comparisons failed; see report')


if __name__=='__main__':
    main()
