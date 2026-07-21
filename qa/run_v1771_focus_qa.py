#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageStat
import hashlib, json, sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
index=(root/'index.html').read_text()
manifest=json.loads((root/'manifest.json').read_text())
sw=(root/'service-worker.js').read_text()
prod=json.loads((root/'assets/scenes/production-manifest-v1729.json').read_text())
checks=[]
def check(name, ok, detail=''):
    checks.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, detail)
check('version:1771', 'const BUILD_VERSION = "1.7.7.1"' in index and manifest.get('version')=='1.7.7.1')
check('cache:bumped', 'briar-crown-v1.7.7.1-tavern-scene-clarity-hotfix' in sw)
check('index:new-scene-urls', 'tavern-approach-v1771.webp' in index and 'tavern-door-v1771.webp' in index)
check('index:no-old-scene-urls', 'tavern-approach-v1770.webp' not in index and 'tavern-door-v1770.webp' not in index)
for name in ['tavern-approach-v1771.webp','tavern-door-v1771.webp']:
    p=root/'assets/scenes'/name
    check(name+':exists',p.exists())
    if p.exists():
        im=Image.open(p).convert('RGB')
        check(name+':dimensions',im.size==(1200,900),str(im.size))
        check(name+':mobile-size',p.stat().st_size<750000,str(p.stat().st_size))
        check(name+':manifest',name in prod['assets'])
        if name in prod['assets']:
            check(name+':checksum',hashlib.sha256(p.read_bytes()).hexdigest()==prod['assets'][name]['sha256'])
        stat=ImageStat.Stat(im)
        brightness=sum(stat.mean)/3
        check(name+':daylight-brightness',brightness>60,f'{brightness:.1f}')
check('manifest:no-old-art', 'tavern-approach-v1770.webp' not in prod['assets'] and 'tavern-door-v1770.webp' not in prod['assets'])
print(f'RESULT {sum(checks)}/{len(checks)}')
raise SystemExit(0 if all(checks) else 1)
