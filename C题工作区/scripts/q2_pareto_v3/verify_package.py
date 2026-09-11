"""Read-only integrity check of the delivered research package."""
import csv
import hashlib
from pathlib import Path

WORK=Path(__file__).resolve().parents[2]
REPORT=WORK/'reports/q2_pareto_v3'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    failures=[]
    with (REPORT/'package_manifest.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    for row in rows:
        p=WORK/row['path']
        if not p.is_file() or p.stat().st_size!=int(row['bytes']) or digest(p)!=row['sha256']:
            failures.append(row['path'])
    print(f'Checked {len(rows)} package files; failures: {len(failures)}')
    for name in failures:print('FAIL',name)
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
