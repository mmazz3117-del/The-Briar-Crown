#!/usr/bin/env python3
"""Fail the build for metadata, referenced-file, or manifest drift."""
from pathlib import Path
import json,re,hashlib,subprocess,sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
out=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'qa-results';out.mkdir(parents=True,exist_ok=True)
r=json.loads((root/'release.json').read_text());s=(root/'index.html').read_text();m=json.loads((root/'manifest.json').read_text());sw=(root/'service-worker.js').read_text();results=[]
def check(name,ok,detail=''):
 results.append({'test':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name)
check('release:app-version',f'const BUILD_VERSION = "{r["version"]}"' in s)
check('release:app-name',f'const BUILD_NAME = "{r["name"]}"' in s)
check('release:web-manifest',m['version']==r['version'] and m['start_url']==f'./index.html?build={r["build"]}')
check('release:cache-version',f'briar-crown-v{r["version"]}' in sw)
check('release:worker-registration',f'service-worker.js?build={r["build"]}' in s)
check('release:deployment-tag',f'name="briar-crown-deployment" content="{r["build"]}"' in s)
check('release:static-label',f'Version {r["version"]} • {r["name"]}' in s)
check('release:save-schema',f'schemaVersion = {r["saveSchema"]}' in s)
refs=set(re.findall(r'assets/[a-zA-Z0-9_/-]+\.(?:png|webp|jpg|svg|json)',s))
refs|={x[2:] for x in re.findall(r'"(\./[^"?]+)"',sw.split('self.addEventListener',1)[0]) if x!='./'}
missing=sorted(x for x in refs if not (root/x).is_file());check('assets:all-static-references',not missing,{'count':len(refs),'missing':missing})
prod=json.loads((root/r['artManifest']).read_text());bad=[]
check('release:art-manifest-version',prod.get('version')==r['artVersion'],{'expected':r['artVersion'],'actual':prod.get('version')})
for name,meta in prod['assets'].items():
 p=root/'assets/scenes'/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:bad.append(name)
check('assets:production-hashes',not bad,{'count':len(prod['assets']),'mismatch':bad})
scene_files={p.name for p in (root/'assets/scenes').glob('*.webp')}
active={Path(x).name for x in refs if x.startswith('assets/scenes/') and x.endswith('.webp')}
check('assets:no-unused-or-unmanifested-scenes',scene_files==active==set(prod['assets']),{'files':len(scene_files),'active':len(active),'manifest':len(prod['assets']),'unused':sorted(scene_files-active),'unmanifested':sorted(scene_files-set(prod['assets']))})
digests={}
for name in scene_files:
 digest=hashlib.sha256((root/'assets/scenes'/name).read_bytes()).hexdigest();digests.setdefault(digest,[]).append(name)
duplicates=[a for a in digests.values() if len(a)>1]
check('assets:no-exact-scene-duplicates',not duplicates,duplicates)
art=json.loads((root/r['itemArtManifest']).read_text());bad=[]
for item,meta in art['items'].items():
 if meta.get('art') and not (root/meta['art']).is_file():bad.append(item)
check('assets:item-art-references',art['schema']==1 and not bad,{'entries':len(art['items']),'custom':sum(bool(x.get('art')) for x in art['items'].values()),'missing':bad})
heroes=['knight','ranger','wizard','rogue','druid','bard']
missing_heroes=[]
for h in heroes:
    avatar=f'assets/characters/{h}-avatar-v17921.webp'
    select=f'assets/characters/{h}-select-v17921.webp'
    if not (root/avatar).is_file() or not (root/select).is_file() or avatar not in s or select not in s:
        missing_heroes.append(h)
check('assets:playable-hero-portraits',not missing_heroes,{'count':len(heroes),'missing':missing_heroes,'mode':'avatar+full-body-selection'})
check('gameplay:authored-scene-lighting','const sceneLightingMap = Object.freeze({' in s and 'document.body.dataset.lighting = currentSceneLighting();' in s)
parts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',s,re.S);tmp=out/'app-syntax-check.js';tmp.write_text('\n'.join(parts))
res=subprocess.run(['node','--check',str(tmp)],capture_output=True,text=True);check('javascript:syntax',res.returncode==0,res.stderr);tmp.unlink()
res=subprocess.run(['node',str(root/'qa/test_service_worker.cjs'),str(root)],capture_output=True,text=True);check('service-worker:handler-fixtures',res.returncode==0,res.stdout+res.stderr)
summary={'passed':sum(x['passed'] for x in results),'total':len(results),'results':results};(out/'release-integrity.json').write_text(json.dumps(summary,indent=2));print(f'{summary["passed"]}/{summary["total"]} passed');sys.exit(0 if all(x['passed'] for x in results) else 1)
