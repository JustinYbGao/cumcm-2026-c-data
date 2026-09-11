"""Restore large ZIPs without overwriting existing files; verify every SHA256."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    for record in manifest['archives']:
        target = WORK/record['path']
        for part in record['parts']:
            source = ROOT/part['path']
            assert source.stat().st_size == part['bytes'] and sha(source) == part['sha256'], source
        if target.exists():
            assert target.stat().st_size == record['bytes'] and sha(target) == record['sha256'], target
            print('Already verified:', record['path'])
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(target.name+'.assembling')
        with staging.open('xb') as output:
            for part in record['parts']:
                with (ROOT/part['path']).open('rb') as source:
                    while chunk := source.read(8*1024*1024):
                        output.write(chunk)
        assert staging.stat().st_size == record['bytes'] and sha(staging) == record['sha256']
        # A hard link fails if the destination appeared concurrently; no overwrite.
        target.hardlink_to(staging)
        staging.unlink()
        print('Restored and verified:', record['path'])


if __name__ == '__main__':
    main()
