"""Fail closed before publishing; inspect staged bytes without printing matches."""
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
result=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=ROOT,check=True,capture_output=True)
paths=[p.decode('utf-8') for p in result.stdout.split(b'\0') if p]
bad=[]
for path in paths:
    if path.endswith('/.env') or path=='.env' or path.startswith(('.runtime/','.venv/','.npm-cache/','DataCoSupplyChainDataset/')):
        bad.append(path)
        continue
    content=subprocess.run(['git','show',':'+path],cwd=ROOT,check=True,capture_output=True).stdout
    if b'\0' in content[:8192]: continue
    if re.search(rb'sk-[A-Za-z0-9_-]{20,}',content) or re.search(rb'-{5}BEGIN PRIVATE KEY-{5}',content):
        bad.append(path)
if bad:
    print('Blocked: potentially sensitive staged files. Inspect locally; matches are not printed.')
    for path in bad: print(path)
    raise SystemExit(1)
print(f'Checked {len(paths)} staged files: no matching API keys or ignored runtime paths.')
