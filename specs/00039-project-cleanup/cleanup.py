"""One-shot cleanup with an explicit inventory; never follows reparse points."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).absolute().parents[2]
OUT = Path(__file__).parent

def digest(p):
    return hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()

def linked(p):
    return bool(p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)

def walk(p):
    yield p
    if p.is_dir() and not linked(p):
        for child in p.iterdir():
            yield from walk(child)

def remove(p):
    if not p.absolute().is_relative_to(ROOT) or p == ROOT:
        raise RuntimeError(str(p))
    if linked(p):
        if p.is_dir():
            os.rmdir(p)
        else:
            p.unlink()
    elif p.is_dir():
        for child in list(p.iterdir()):
            remove(child)
        p.rmdir()
    else:
        p.chmod(stat.S_IWRITE | stat.S_IREAD)
        p.unlink()

tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
before = {n: digest(ROOT / n) for n in tracked if n and (ROOT / n).is_file()}
venv = ROOT / '.venv/Scripts/python.exe'
venv_hash = digest(venv)
targets = [p for p in ROOT.iterdir() if p.is_dir() and
           (p.name.startswith('.pytest_tmp') or p.name in ('.pytest_cache', '.ruff_cache'))]
targets += [ROOT / n for n in ('temp/refactor-038-baseline', 'temp/refactor-038-runtime',
                              'temp/refactor-038-path-test.py') if (ROOT / n).exists()]
for name in ('src', 'backend', 'Tests', 'scripts', 'archive', 'scratch'):
    for base, dirs, files in os.walk(ROOT / name, followlinks=False):
        dirs[:] = [d for d in dirs if not linked(Path(base) / d)]
        if '__pycache__' in dirs:
            targets.append(Path(base) / '__pycache__')
            dirs.remove('__pycache__')
inventory = []
for target in targets:
    nodes = list(walk(target))
    if any((ROOT / n).is_relative_to(target) for n in before):
        raise RuntimeError('Tracked cleanup target: ' + str(target))
    inventory.append({'path': str(target.relative_to(ROOT)),
                      'files': sum(p.is_file() and not linked(p) for p in nodes),
                      'bytes': sum(p.stat().st_size for p in nodes if p.is_file() and not linked(p)),
                      'links': [str(p.relative_to(ROOT)) for p in nodes if linked(p)]})
groups = {}
for n, h in before.items():
    if (ROOT / n).stat().st_size:
        groups.setdefault(h, []).append(n)
duplicates = [names for names in groups.values() if len(names) > 1]
report = {'inventory': inventory, 'tracked_duplicates': duplicates,
          'total_bytes': sum(i['bytes'] for i in inventory), 'deleted': False}
(OUT / 'inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
if '--apply' in sys.argv:
    for p in targets:
        remove(p)
    report.update(deleted=True, all_targets_absent=all(not p.exists() for p in targets),
                  tracked_unchanged=all((ROOT / n).exists() and digest(ROOT / n) == h for n, h in before.items()),
                  venv_unchanged=venv.exists() and digest(venv) == venv_hash)
    (OUT / 'inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in ('inventory', 'tracked_duplicates')}))
print('Targets:', len(inventory), 'Duplicate groups:', len(duplicates))
