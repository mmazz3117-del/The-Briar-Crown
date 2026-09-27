#!/usr/bin/env python3
"""Safe-deletion regression checks. All writes are confined to a temporary folder."""
from pathlib import Path
import hashlib,json,sys,tempfile
from cleanup_retired import clean
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'qa-results';OUT.mkdir(parents=True,exist_ok=True)
results=[]
def check(name,ok):
 results.append({'test':name,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name)
with tempfile.TemporaryDirectory() as d:
 root=Path(d)/'repo';root.mkdir();(root/'index.html').write_text('fixture');(root/'release.json').write_text('{"version":"1.7.9.1"}')
 known=root/'retired.webp';known.write_bytes(b'old');entry={'path':'retired.webp','sha256':[hashlib.sha256(b'old').hexdigest()]}
 rows=clean(root,[entry]);check('retirement:dry-run-keeps-file',known.exists() and rows[0]['status']=='retired-unchanged')
 rows=clean(root,[entry],True);check('retirement:apply-removes-known-bytes',not known.exists() and rows[0]['status']=='removed')
 rows=clean(root,[entry],True);check('retirement:repeat-is-idempotent',rows[0]['status']=='already-absent')
 known.write_bytes(b'user modification');rows=clean(root,[entry],True);check('retirement:modified-file-preserved',known.read_bytes()==b'user modification' and rows[0]['status']=='modified-keep')
 other=root/'keep.txt';other.write_text('user file');clean(root,[entry],True);check('retirement:unrelated-file-preserved',other.read_text()=='user file')
 outside=Path(d)/'outside.webp';outside.write_bytes(b'old');rows=clean(root,[{'path':'../outside.webp','sha256':entry['sha256']}],True);check('retirement:path-traversal-blocked',outside.exists() and rows[0]['status']=='unsafe-path')
 link=root/'linked.webp';link.symlink_to(outside);rows=clean(root,[{'path':'linked.webp','sha256':entry['sha256']}],True);check('retirement:symlink-preserved',outside.exists() and link.is_symlink() and rows[0]['status']=='unsafe-symlink')
 (root/'release.json').write_text('{"version":"1.7.8.9"}')
 try:clean(root,[entry],True);blocked=False
 except ValueError:blocked=True
 check('retirement:wrong-root-version-blocked',blocked)
catalog=json.loads((ROOT/'qa/retired-files.json').read_text(encoding='utf-8'))['files']
check('retirement:catalog-excludes-current-package-files', all(not (ROOT/e['path']).exists() for e in catalog))
summary={'passed':sum(r['passed'] for r in results),'total':len(results),'results':results};(OUT/'cleanup-safety.json').write_text(json.dumps(summary,indent=2)+'\n');print(f'{summary["passed"]}/{summary["total"]} passed');sys.exit(0 if summary['passed']==summary['total'] else 1)
