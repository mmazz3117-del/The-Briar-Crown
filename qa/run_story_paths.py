#!/usr/bin/env python3
"""Command-driven main-story paths for all six classes and both endings.
No progression flags, inventory items, or reset helpers are injected. Each run
uses the actual New Adventure entry point after the previous ending.
Storage is a Map-backed fixture; no real iOS or offline validation is implied.
Usage: python story_paths.py [game_directory] [output_directory]
"""
from pathlib import Path
import sys,json,shutil,os
VARIANT=os.environ.get("BRIAR_STORY_VARIANT","canonical")
from playwright.sync_api import sync_playwright
ROOT=(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]).resolve()
OUT=(Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'qa-results').resolve();OUT.mkdir(parents=True,exist_ok=True)
html=ROOT.joinpath('index.html').read_text();shim="""<script>const auditStore=new Map([['briar-crown-music-enabled','false']]);Object.defineProperty(window,'localStorage',{value:{getItem:k=>auditStore.get(k)||null,setItem:(k,v)=>auditStore.set(k,String(v)),removeItem:k=>auditStore.delete(k)}});</script>""";html=html.replace('<head>',f'<head><base href="file://{ROOT}/">'+shim,1)
# Each step is (command, expected room). No silent recovery or teleportation.
steps=[('east','forgeLane'),('north','forgeDoor'),('enter forge','blacksmith'),('talk to blacksmith','blacksmith'),('leave forge','forgeDoor'),('south','forgeLane'),('east','eastRoad'),('east','forestEdge'),('take silver token','forestEdge'),('east','willowTrail'),('east','flowerClearing'),('east','fallenLog'),('east','whisperingForest'),('north','cottageApproach'),('open cottage door','cottageApproach'),('enter cottage','cottage'),('open cabinet','cottage'),('take silver key','cottage'),('move rug','cottage'),('use silver key on trapdoor','cottage'),('open trapdoor','cottage'),('down','cellar'),('take ferry crank','cellar'),('take lantern','cellar'),('up','cottage'),('south','cottageApproach'),('south','whisperingForest'),('south','moonfen'),('use ferry crank on winch','moonfen'),('east','hutExterior'),('enter hut','hutInterior'),('take fairy coin','hutInterior'),('west','hutExterior'),('west','moonfen'),('north','moonwell'),('use iron hook on well','moonwell')]
return_square=[('west',r) for r in ['whisperingForest','fallenLog','flowerClearing','willowTrail','forestEdge','eastRoad','forgeLane','square']]
chapel=[('west','chapelRoad'),('west','chapelYard'),('north','chapelApproach'),('enter chapel','chapel'),('use fairy coin on statue','chapel'),('down','crypt'),('use silver token on reliquary','crypt'),('take sun sigil','crypt'),('up','chapel'),('south','chapelApproach'),('south','chapelYard'),('east','chapelRoad'),('east','square')]
to_well=[('east',r) for r in ['forgeLane','eastRoad','forestEdge','willowTrail','flowerClearing','fallenLog','whisperingForest','moonwell']]
final=[('south',r) for r in ['castleRoad','thornHedgePass','brokenWatchCrossing','outerGateApproach','castleGate']]+[('use crown shard on gate','castleGate'),('confirm ending','castleGate')]
results=[]
with sync_playwright() as p:
 launch={'headless':True,'args':['--no-sandbox','--allow-file-access-from-files']}
 if shutil.which('chromium'):launch['executable_path']=shutil.which('chromium')
 browser=p.chromium.launch(**launch)
 page=browser.new_page(viewport={'width':390,'height':844});page.set_default_timeout(5000);page.set_content(html,wait_until='load')
 for key in ['knight','ranger','wizard','rogue','druid','bard']:
  for ending in ['thorn','dawn']:
   page.evaluate("async key=>{selectedHeroClass=key;await beginAdventure()}",key)
   path=steps+return_square+chapel+(to_well+[('use sun sigil on cage','moonwell')]+return_square if ending=='dawn' else [])+final
   trace=[];ok=True
   for i,(command,expected) in enumerate(path):
    if VARIANT=='alternate' and command.startswith('use ') and ' on ' in command:
     item,target=command[4:].split(' on ',1);command=f'give {item} to {target}' 
    observed=page.evaluate("async command=>{await processCommand(command);return {room:state.room,log:state.log.slice(-2),ending:state.flags.ending}}",command)
    trace.append({'step':i+1,'command':command,'expectedRoom':expected,**observed})
    if observed['room']!=expected:
     ok=False;break
   state=page.evaluate("({ending:state.flags.ending,fairyFreed:state.flags.fairyFreed,inventory:state.inventory,flags:{ferryRepaired:state.flags.ferryRepaired,cryptOpen:state.flags.cryptOpen,reliquaryOpen:state.flags.reliquaryOpen},health:state.health,turns:state.turns})")
   result={'class':key,'targetEnding':ending,'passed':ok and state['ending']==ending,'commandsRun':len(trace),'state':state,'trace':trace};results.append(result)
   (OUT/f'story_paths_{VARIANT}.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='trace'}),flush=True)
 page.screenshot(path=str(OUT/'ending-mobile.png'),full_page=True);browser.close()

print(f"Story journeys: {sum(x['passed'] for x in results)}/{len(results)} passed")
sys.exit(0 if all(x["passed"] for x in results) and len(results)==12 else 1)
