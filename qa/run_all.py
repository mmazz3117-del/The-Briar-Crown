#!/usr/bin/env python3
"""One release entry point. Runs every current suite and retains all results."""
from pathlib import Path
import sys,subprocess,json
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
out=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'qa-results';out.mkdir(parents=True,exist_ok=True)
results=[]
for script in ['check_release.py','run_qa.py','run_stabilization.py','run_consistency.py','run_cleanup_smoke.py','run_cleanup_safety.py','run_story_paths.py']:
 args=[sys.executable,str(root/'qa'/script),str(root)]
 if script!='run_qa.py':args.append(str(out))
 print('\nRUN',script,flush=True)
 with (out/(script.removesuffix('.py')+'.log')).open('w') as log:
  proc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
 results.append({'suite':script,'passed':proc.returncode==0,'exitCode':proc.returncode})
 print(('PASS' if proc.returncode==0 else 'FAIL'),script,flush=True)
(out/'all-suites.json').write_text(json.dumps(results,indent=2))
sys.exit(0 if all(x['passed'] for x in results) else 1)
