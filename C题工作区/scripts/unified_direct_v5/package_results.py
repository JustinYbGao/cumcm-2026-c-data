"""Preserve legacy hashes and inventory the five new version directories."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

WORK=Path(__file__).resolve().parents[2];REPORT=WORK/'reports/unified_direct_v5'
ROOTS=[WORK/name/'unified_direct_v5' for name in ['scripts','configs','results','reports','outputs']]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):h.update(data)
    return h.hexdigest()


def save(name,obj):
    (REPORT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def preserve():
    before=json.loads((REPORT/'protected_before.json').read_text());after={};changes=[]
    for rel,original in before.items():
        path=WORK/rel;actual=sha(path) if path.is_file() else None;after[rel]=actual
        if actual!=original:changes.append(rel)
    save('protected_after.json',after)
    frozen=json.loads((REPORT/'protocol_freeze.json').read_text())['sha256']
    protocol=[rel for rel,value in frozen.items() if sha(WORK/rel)!=value]
    source=json.loads((REPORT/'independent_sources.json').read_text())['metrics']['source_hashes']
    source_changes=[rel for rel,value in source.items() if sha(WORK.parent/rel)!=value]
    status=subprocess.run(['git','status','--short'],cwd=WORK,text=True,capture_output=True,check=True).stdout
    diff=subprocess.run(['git','diff','--name-only'],cwd=WORK,text=True,capture_output=True,check=True).stdout
    metadata_changes=[];research_changes=[]
    for rel in changes:
        if Path(rel).name=='.DS_Store':
            metadata_changes.append({'path':rel,'before_sha256':before[rel],'after_sha256':after[rel],
                'kind':'macOS directory metadata','cause':'not attributed; no task script intentionally writes this file; original bytes unavailable for restoration'})
        else:research_changes.append(rel)
    result={'passed':not(research_changes or protocol or source_changes or diff),'all_prior_files_byte_identical':not changes,
        'protected_files':len(before),'unchanged_protected_files':len(before)-len(changes),'changed_legacy_files':changes,
        'changed_research_files':research_changes,'metadata_exceptions':metadata_changes,
        'frozen_production_files':len(frozen),'changed_frozen_files':protocol,'original_source_workbooks':len(source),'changed_source_workbooks':source_changes,
        'git_status':status,'tracked_diff':diff,'source_before':'protected_before.json','source_after':'protected_after.json',
        'scope':'Prior research artifacts must remain byte-identical; any .DS_Store metadata change explicitly disclosed and excluded from research-artifact verdict. Original Appendix1-4 also checked; templates checked by workbook readback.'}
    save('preservation_check.json',result);assert result['passed'],result
    return result


def package():
    excluded={REPORT/name for name in ['package_manifest.json','SHA256SUMS.txt','package_readback.json']}
    files=[];symlinks=[]
    for root in ROOTS:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():symlinks.append({'path':str(path.relative_to(WORK)),'target':str(path.resolve())});continue
            if not path.is_file() or path in excluded:continue
            files.append({'path':str(path.relative_to(WORK)),'bytes':path.stat().st_size,'sha256':sha(path)})
    save('package_manifest.json',{'format':'five-directory versioned result package','files':files,'symlinks_external_dependencies':symlinks,
       'excluded_self_referential_control_files':[str(p.relative_to(WORK)) for p in sorted(excluded)]})
    sums=''.join(f"{row['sha256']}  {row['path']}\n" for row in files);(REPORT/'SHA256SUMS.txt').write_text(sums)
    # Read the saved manifest and every listed byte stream again, not the in-memory objects.
    saved=json.loads((REPORT/'package_manifest.json').read_text());errors=[]
    for row in saved['files']:
        path=WORK/row['path']
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:errors.append(row['path'])
    actual={str(p.relative_to(WORK)) for root in ROOTS for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p not in excluded}
    listed={row['path'] for row in saved['files']};assert actual==listed
    result={'passed':not errors,'files':len(saved['files']),'total_bytes':sum(row['bytes'] for row in saved['files']),'mismatches':errors,
        'manifest_sha256':sha(REPORT/'package_manifest.json'),'checksum_list_sha256':sha(REPORT/'SHA256SUMS.txt'),
        'scope':'saved manifest readback; every listed file reread and hashed; all files in five roots covered except three self-referential control files; dependency symlinks disclosed'}
    save('package_readback.json',result);assert result['passed'];print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--preserve-only',action='store_true');args=p.parse_args()
    print(json.dumps(preserve(),ensure_ascii=False,indent=2))
    if not args.preserve_only:package()
