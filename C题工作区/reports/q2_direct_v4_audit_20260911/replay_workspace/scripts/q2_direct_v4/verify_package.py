"""Re-read archive, embedded manifest and every file without trusting build status."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

WORK=Path(__file__).resolve().parents[2];REPORT=WORK/'reports/q2_direct_v4'
archive=REPORT/'q2_direct_v4_review.zip'
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
assert sha==(REPORT/(archive.name+'.sha256')).read_text().split()[0]
with zipfile.ZipFile(archive) as z:
    name='reports/q2_direct_v4/package_manifest.csv';rows=list(csv.DictReader(io.StringIO(z.read(name).decode())))
    assert set(z.namelist())=={row['path'] for row in rows}|{name}
    for row in rows:
        content=z.read(row['path']);assert len(content)==int(row['bytes'])
        assert hashlib.sha256(content).hexdigest()==row['sha256'],row['path']
    assert z.testzip() is None
print(json.dumps(dict(passed=True,files=len(rows),zip_sha256=sha,zip_bytes=archive.stat().st_size),indent=2))
