"""Source-package sanity checks; does not replace a complete end-to-end runtime test."""
import ast
import pathlib
import re
import sys
root=pathlib.Path(__file__).resolve().parents[1]
pyfiles=list((root/'backend').rglob('*.py'))
for p in pyfiles:
    ast.parse(p.read_text(encoding='utf8'),filename=str(p))
assert len(list((root/'sample_documents').glob('*.txt')))>=20
needed=['backend/app/main.py','backend/app/agents.py','backend/app/retrieval.py',
        'backend/app/ingestion.py','backend/app/reports.py','frontend/package.json',
        'frontend/src/App.jsx','README.md','.env.example','docker-compose.yml']
assert all((root/rel).is_file() for rel in needed)
assert not (root/'frontend'/'node_modules').exists() or (root/'frontend'/'node_modules').is_dir()
print(f'PASS: {len(pyfiles)} Python source files parsed; {len(list((root/"sample_documents").glob("*.txt")))} synthetic documents; all critical files exist.')
print('For full testing run: python -m pytest backend/tests -q and npm run build after dependency installation.')
