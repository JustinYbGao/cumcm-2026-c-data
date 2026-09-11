"""Freeze supplemental sources, results and paper parts into disjoint ZIPs."""
import hashlib
import json
from pathlib import Path
import zipfile
WORK=Path(__file__).resolve().parents[1];OUT=WORK/'deliverables/robustness/v1_continuous_audit'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    if OUT.exists():raise FileExistsError('Frozen package exists; preserve it and use a new version')
    for rel in ['results/robustness/validation.json','results/robustness/lp_audit.json','results/robustness/analysis_validation.json','papers/assembly_v1/assembly_validation.json']:
        assert json.loads((WORK/rel).read_text())['passed'],rel
    for name in ['robustness_effects','robustness_monthly']:
        root=WORK/'reports/figures/modelviz_robustness_v1_en'/name
        assert json.loads((root/'workspace/final_quality_report.json').read_text())['passed']
        visual=json.loads((root/'workspace/assistant_visual_assessment.json').read_text())
        assert sha(root/'outputs/chart.png')==visual['inspected_png_sha256']
        assert sha(root/'workspace/adapted_plot.py')==visual['inspected_script_sha256']
    files=set()
    hashes=json.loads((WORK/'results/robustness/input_code_hashes_before.json').read_text())
    for rel,digest in hashes.items():
        assert sha(WORK/rel)==digest,rel
        files.add(WORK/rel)
    for root in ['results/robustness','reports/robustness','logs/robustness','reports/figures/modelviz_robustness_v1_en','papers/assembly_v1']:
        files.update(p for p in (WORK/root).rglob('*') if p.is_file())
    for pattern in ['scripts/*robustness*.py','tests/test_robustness*.py','scripts/modelviz/robustness*.py','papers/*draft.md']:
        files.update(WORK.glob(pattern))
    for rel in ['scripts/assemble_paper.py','scripts/modelviz_revision.py','scripts/audit_innovation_lp.py','scripts/audit_q3_lp.py','requirements.txt','requirements-q3.txt','results/q3/all_A/ledger.csv','results/q2/selected/models_and_solvers.json','reports/q2_representative_tables.md','reports/q3_representative_tables.md','reports/q4_representative_tables.md']:
        files.add(WORK/rel)
    # Include displayed older images; their frozen result packages remain separate archives.
    for root in ['modelviz_v3_en','modelviz_q3_v1_en','modelviz_q4_v1_en','modelviz_innovation_v1_en']:
        for ext in ['png','svg']:files.update((WORK/'reports/figures'/root).glob(f'*/outputs/chart.{ext}'))
    files={p for p in files if '__pycache__' not in p.parts and p.suffix!='.pyc'}
    for p in files:assert p.exists(),p
    OUT.mkdir(parents=True)
    (OUT/'README.md').write_text('''# 连续策略与论文装配结果包（内部假设版）

按archive_index.json下载本目录全部part ZIP，解压到同一目录；各ZIP成员不重叠，不是二进制分卷。解压后形成C题工作区的相对目录结构。先读papers/assembly_v1/00_README_装配顺序.md，再读papers/robustness_draft.md。全部原五份初稿保留。

manifest.json记录所有源文件相对于工作区的路径、字节数和SHA-256。验证脚本以自身位置推导工作区，不依赖原用户绝对目录；论文中的绝对图文链接服务于当前Codex预览，迁移后按相同相对路径调整。

复核命令（在解压根目录配置同依赖Python环境后）：
```
python -B scripts/validate_robustness.py
python -B scripts/audit_robustness_lp.py
python -B scripts/analyze_robustness.py
python -B -m unittest discover -s tests -p 'test_robustness*.py'
```

run_robustness.py会拒绝覆盖已完成结果；从头求解应另建副本，仅准备必要输入和空results/robustness，不删除此冻结包。图形可直接运行各图workspace/adapted_plot.py并提供DATA_PATH、OUTPUT_DIR；完整ModelViz流程依赖本地skill。内部时间/市场/效率口径尚待确认，不包含正式Excel。此前各问大包仍在原deliverables/q1—q4及innovation，本包不重复封装。
''')
    manifest={str(p.relative_to(WORK)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)}
    write(OUT/'manifest.json',{'file_count':len(manifest),'files':manifest,'scope':'Internal continuous replay, validation and ordered paper draft; no formal Excel'})
    archives=[];members=[];number=0;archive=None
    for p in sorted(files):
        if archive is None or archive.fp.tell()>75*1024*1024:
            if archive is not None:archive.close()
            number+=1;path=OUT/f'v1_continuous_audit.part{number:02d}.zip'
            archive=zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6);archives.append(path)
        name=str(p.relative_to(WORK));archive.write(p,name);members.append(name)
    if archive:archive.close()
    seen=[]
    for path in archives:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            for name in z.namelist():
                assert hashlib.sha256(z.read(name)).hexdigest()==manifest[name]['sha256'],name
                seen.append(name)
    assert sorted(seen)==sorted(manifest) and len(set(seen))==len(seen)
    assert all(sha(WORK/name)==row['sha256'] for name,row in manifest.items())
    write(OUT/'archive_index.json',{'file_count':len(manifest),'archives':[{'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in archives],'extraction':'Extract all disjoint ZIPs into one directory'})
    write(OUT/'package_validation.json',{'passed':True,'file_count':len(manifest),'archives':len(archives),'all_source_and_member_hashes_match':True,'no_duplicate_or_missing_members':True,'archive_crc_passed':True})
    print(json.dumps({'passed':True,'files':len(manifest),'archives':[(p.name,p.stat().st_size) for p in archives]},indent=2))

if __name__=='__main__':main()
