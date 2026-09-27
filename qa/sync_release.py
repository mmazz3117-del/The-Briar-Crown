#!/usr/bin/env python3
"""Synchronize active build labels from release.json; historical art filenames stay intact.
Run after intentionally editing release.json. The QA suite separately verifies outputs.
"""
from pathlib import Path
import json,re,sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
r=json.loads((root/'release.json').read_text());v,b,n=r['version'],r['build'],r['name']
p=root/'index.html';s=p.read_text()
s=re.sub(r'(<meta name="briar-crown-deployment" content=")[^"]+',r'\g<1>'+b,s)
s=re.sub(r'(<title>The Briar Crown — Mobile Adventure v)[^<]+',r'\g<1>'+v,s)
s=re.sub(r'const BUILD_VERSION = "[^"]+";',f'const BUILD_VERSION = "{v}";',s)
if 'const BUILD_NAME = ' in s:s=re.sub(r'const BUILD_NAME = "[^"]+";',f'const BUILD_NAME = "{n}";',s)
else:s=s.replace(f'const BUILD_VERSION = "{v}";',f'const BUILD_VERSION = "{v}";\n    const BUILD_NAME = "{n}";')
s=re.sub(r'(<small id="version-tag">)[^<]+',r'\g<1>'+f'Version {v} • {n}',s)
s=re.sub(r'const versionLabel=`Version \$\{BUILD_VERSION\}[^`]+`;',r'const versionLabel=`Version ${BUILD_VERSION} • ${BUILD_NAME}`;',s)
s=re.sub(r'service-worker.js\?build=\d+',f'service-worker.js?build={b}',s)
p.write_text(s)
p=root/'manifest.json';d=json.loads(p.read_text());d.update(version=v,start_url=f'./index.html?build={b}',description='The Briar Crown mobile illustrated fantasy adventure: parallel typed and tapped exploration, consistent item effects, protected new-game state, and save import/export.');p.write_text(json.dumps(d,indent=2)+'\n')
p=root/'service-worker.js';s=p.read_text();s=re.sub(r'const CACHE = "[^"]+";',f'const CACHE = "briar-crown-v{v}-stabilization";',s);p.write_text(s)
p=root/'qa/contracts.json';d=json.loads(p.read_text());d['version']=v;p.write_text(json.dumps(d,indent=2)+'\n')
print(f'Synchronized build {v} ({b})')
