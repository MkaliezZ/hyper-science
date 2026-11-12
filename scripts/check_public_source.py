"""Check the release boundary and pinned upstream/source integrity; not a secret scanner."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
vendor = root/'src/base/app/research/functional/vendor/scientific_agent_skills'
manifest = json.loads((vendor/'manifest.json').read_text(encoding='utf8'))
for name, expected in manifest['files'].items():
    assert hashlib.sha256((vendor/name).read_bytes()).hexdigest() == expected, name
snapshot = json.loads((root/'docs/source-snapshot.json').read_text(encoding='utf8'))
for name, expected in snapshot['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, name
excluded = {'.git','data','artifacts','build','dist','node_modules','research-runtime','__pycache__','.pytest_cache'}
paths = [p for p in root.rglob('*') if p.is_file() and not any(s in excluded or s.startswith('.venv') or s.endswith('.egg-info') for s in p.relative_to(root).parts)]
for p in paths:
    assert p.suffix.lower() not in {'.sqlite','.sqlite3','.db','.pem','.key','.log','.exe','.zip'}, str(p)
    assert p.name not in {'.env','owner-token.txt','qa-launch-url.txt','running.json'}, str(p)
assert all((vendor/n/'SKILL.md').is_file() for n in ['experimental-design','simpy','scientific-critical-thinking'])
print(json.dumps({'ok':True,'upstream_files':len(manifest['files']),'snapshot_files':len(snapshot['files']),'release_files':len(paths),'scope':'boundary-and-pinned-file-integrity; run credential scanner separately'}))
