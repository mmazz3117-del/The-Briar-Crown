#!/usr/bin/env python3
"""Real rendered-control tests and source-backed visual inventory.
Assets are fulfilled from the package at a test origin; storage is a deterministic
Map fixture. This does not certify browser persistence, Safari, or a live PWA.
"""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,sys,shutil,mimetypes,hashlib,traceback,base64
from playwright.sync_api import sync_playwright
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'qa-results'
OUT.mkdir(parents=True,exist_ok=True)
results=[]
def check(name,ok,detail=None):
 results.append(dict(test=name,passed=bool(ok),detail=detail));print(('PASS ' if ok else 'FAIL ')+name,flush=True)
with sync_playwright() as p:
 launch=dict(headless=True,args=['--no-sandbox'])
 if shutil.which('chromium'):launch['executable_path']=shutil.which('chromium')
 b=p.chromium.launch(**launch);page=b.new_page(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,accept_downloads=True)
 page.set_default_timeout(4000);errors=[];missing=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
 # Test-only image proves the renderer path without adding fake finished artwork.
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
 def serve(route):
  name=unquote(urlsplit(route.request.url).path.lstrip('/'));path=(ROOT/name).resolve();headers={'Access-Control-Allow-Origin':'*'}
  if name=='assets/items/test-fixture.png':route.fulfill(body=png,content_type='image/png',headers=headers)
  elif path.is_relative_to(ROOT) and path.is_file():route.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream',headers=headers)
  else:
   if name!='assets/items/intentionally-missing.png':missing.append(name)
   route.fulfill(status=404,body='Not found',headers=headers)
 page.route('https://briar-crown.test/**',serve)
 shim="""<script>window.qaStore=new Map([['briar-crown-music-enabled','false']]);Object.defineProperty(window,'localStorage',{value:{getItem:k=>qaStore.get(k)??null,setItem:(k,v)=>qaStore.set(k,String(v)),removeItem:k=>qaStore.delete(k)}});</script>"""
 html=(ROOT/'index.html').read_text().replace('<head>','<head><base href="https://briar-crown.test/">'+shim,1)
 page.set_content(html,wait_until='load');ev=page.evaluate
 def reset(room='square'):
  ev("""r=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());state=initialState();state.room=r;resetAdventurePresentation();restoreDynamicExits();state.flags.tutorialSceneTapComplete=true;state.flags.commandTutorialDone=true;document.getElementById('start-overlay').hidden=true;Math.random=()=>.2;renderAll()}""",room)
 try:
  page.wait_for_function('!!document.querySelector(".scene-image")?.naturalWidth')
  check('assets:actual-scene-decodes',True)
  # Produce the complete canonical item registry before testing the real loader.
  ids=ev('Array.from(new Set([...Object.keys(itemInfo),...Object.keys(equipmentInfo),...Object.keys(apothecaryShop),...Object.keys(forgeShop),...Object.keys(consumableItemCatalog),...Object.keys(itemInspectionMeta)].map(canonicalItemId))).sort()')
  registry=json.loads((ROOT/'assets/items/manifest.json').read_text())
  check('item-art:all-known-items-have-records',set(ids)<=set(registry['items']),{'known':len(ids),'recorded':len(registry['items'])})
  (OUT/'known-items.json').write_text(json.dumps(ids,indent=2))
  reset();ev('loadItemArtworkManifest()');page.wait_for_timeout(180);ev("addItem('spell crystal');showItemInspection('spell crystal')");page.wait_for_timeout(120)
  check('item-art:package-custom-art',ev('document.querySelector(".inspection-art").dataset.artStatus==="custom-art"'))
  ev("installItemArtworkManifest({schema:1,items:{'spell crystal':{art:'assets/items/test-fixture.png',alt:'Test only'}}});showItemInspection('spell crystal')")
  page.wait_for_function('document.querySelector(".inspection-art").dataset.artStatus==="custom-art"')
  check('item-art:custom-image-pipeline',ev('document.querySelector(".inspection-art img").naturalWidth===1'))
  ev("installItemArtworkManifest({schema:1,items:{'spell crystal':{art:'assets/items/intentionally-missing.png'}}});showItemInspection('spell crystal')")
  page.wait_for_timeout(150)
  check('item-art:broken-image-fallback',ev('document.querySelector(".inspection-art").dataset.artStatus==="icon-fallback"'))
  check('item-art:remote-path-rejected',ev("()=>{try{installItemArtworkManifest({schema:1,items:{x:{art:'https://example.com/x.png'}}});return false}catch(e){return true}}"))
  ev('loadItemArtworkManifest()')
  reset();ev("addItem('hunting knife');showItemInspection('hunting knife')")
  page.locator('[data-inspection-use]').click()
  check('inspection:weapon-can-target-puzzles',ev("inputEl.value==='use hunting knife on '"))
  # The two visible information entry points agree for representative gear.
  reset();ev("addItem('spell crystal');showInventory()")
  page.locator('[data-examine-item="spell crystal"]').click()
  check('inspection:actual-satchel-examine',page.locator('#item-inspection-dialog').is_visible())
  # Physical taps on puzzle targets, followed by the actual offered action button.
  pairs=[('cottage','silver key','trapdoor','Trapdoor','trapdoorUnlocked'),('chapel','fairy coin','statue','Statue','cryptOpen'),('crypt','silver token','reliquary','Reliquary','reliquaryOpen'),('moonfen','ferry crank','winch','Ferry Winch','ferryRepaired'),('moonwell','sun sigil','cage','Fairy Cage','fairyFreed'),('castleGate','crown shard','gate','Gate','gateShardReady')]
  for room,item,target,label,flag in pairs:
   reset(room);ev("i=>{addItem(i);state.flags.rugMoved=true;renderAll()}",item);page.wait_for_timeout(850)
   try:
    page.get_by_role('button',name='Explore '+label,exact=True).click(timeout=1800)
    page.locator(f'[data-action-command="use {item} on {target}"]').click(timeout=1800)
    check('puzzle:actual-tap:'+item,ev('f=>!!state.flags[f]',flag))
   except Exception as e:check('puzzle:actual-tap:'+item,False,{'error':str(e),'room':ev('state.room'),'selection':ev('selectedHotspotContext'),'actions':ev('Array.from(document.querySelectorAll(".quick-btn")).map(b=>b.textContent)')})
  # Real menu export/download/import controls, not a serialization-only claim.
  reset();ev("state.gold=37;addItem('silver key');addItem('healing herbs',2);state.flags.ferryRepaired=true;restoreDynamicExits();document.getElementById('menu-dialog').showModal()")
  with page.expect_download() as download:page.locator('#export-save-btn').click()
  file=OUT/'test-save-export.json';download.value.save_as(str(file));saved=json.loads(file.read_text())
  check('save:actual-download',saved['format']=='briar-crown-save' and saved['state']['gold']==37)
  reset();page.locator('#import-save-file').set_input_files(str(file));page.wait_for_timeout(150)
  check('save:actual-file-import',ev("state.gold===37&&has('silver key')&&itemQty('healing herbs')===2&&rooms.moonfen.exits.east==='hutExterior'"))
  # Invalid import cancels safely and never overwrites the good on-device fixture.
  before=ev('storageGet(SAVE_KEY)');bad=OUT/'test-invalid-save.json';bad.write_text('{"room":"square","inventory":null}')
  page.locator('#import-save-file').set_input_files(str(bad));page.wait_for_timeout(100)
  check('save:bad-import-keeps-live-and-saved',ev("state.gold===37&&has('silver key')") and ev('storageGet(SAVE_KEY)')==before)
  reset();ev("state.health=7;addItem('healing herbs',2);startCombat('thornHound');beginCombatFromEncounter();state.combat.phase='enemy-ready';saveGame()")
  ev('loadGame()');page.wait_for_timeout(100)
  check('save:combat-resumes-in-same-phase',ev("state.combat?.phase==='enemy-ready'&&document.getElementById('combat-dialog').open&&state.health===7"))
  reset();ev("startCombat('thornHound');saveGame();loadGame()");page.wait_for_timeout(100)
  check('save:encounter-intro-resumes',ev("state.pendingEncounter==='thornHound'&&document.getElementById('encounter-dialog').open"))
  reset();ev("combatVictory('thornHound');saveGame();loadGame()");page.wait_for_timeout(100)
  check('save:pending-loot-resumes',ev("state.pendingLoot?.enemyId==='thornHound'&&document.getElementById('loot-dialog').open"))
  before=ev('state.gold');page.locator('#loot-collect-btn').click();ev('collectPendingLoot()')
  check('save:restored-loot-is-collected-once',ev('state.gold')==before+3 and ev("itemQty('field bandage')===1&&!state.pendingLoot"))
  # Complete visual inventory from the same selector and hotspot code used at runtime.
  reset();data=ev("""()=>{const records=[];for(const id of Object.keys(rooms)){for(const view of Object.keys(directionalRooms[id]?.images||{center:1})){for(const stage of ['fresh','completed']){state=initialState();state.room=id;state.view=view;if(stage==='completed'){for(const [key,value] of Object.entries(state.flags))if(typeof value==='boolean')state.flags[key]=true;state.flags.ending='dawn';}restoreDynamicExits();records.push({id:`${id}:${view}:${stage}`,room:id,name:rooms[id].name,view,stage,...currentScenePresentation(),hotspots:currentHotspots(),description:directionalRooms[id]?.descriptions[view]||rooms[id].description});}}}state=initialState();state.room='secretAlcove';state.flags.tunnelCoinsFound=true;records.push({id:'secretAlcove:center:coins-visible',room:state.room,name:rooms[state.room].name,view:'center',stage:'coins-visible',...currentScenePresentation(),hotspots:currentHotspots(),description:rooms[state.room].description});return records;}""")
  for rec in data:
   asset=ROOT/rec['imagePath'];rec['sha256']=hashlib.sha256(asset.read_bytes()).hexdigest() if asset.is_file() else None
   rec['descriptionSha256']=hashlib.sha256(str(rec['description']).encode()).hexdigest()
   rec['hotspotSha256']=hashlib.sha256(json.dumps(rec['hotspots'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
   ok=asset.is_file() and all(isinstance(h.get(k),(int,float)) for h in rec['hotspots'] for k in ['x','y','w','h'])
   ok=ok and all(0<=h['x']<=100 and 0<=h['y']<=100 and 0<h['w']<=100 and 0<h['h']<=100 and h.get('command') for h in rec['hotspots'])
   check('scene:asset-and-hotspot-integrity:'+rec['id'],ok)
  (OUT/'scene-snapshots.json').write_text(json.dumps(data,indent=2))
  unique=sorted({r['imagePath'] for r in data});bad=[]
  for asset in unique:
   good=ev("p=>new Promise(resolve=>{const i=new Image;i.onload=()=>resolve(i.naturalWidth>=1200);i.onerror=()=>resolve(false);i.src=p})",asset)
   if not good:bad.append(asset)
  check('scene:all-active-images-decode',not bad,{'count':len(unique),'failures':bad})
  # Optional geometry/art drift gate; inventory generation can run before the baseline exists.
  review=ROOT/'qa/scene-review.json'
  if review.exists():
   expected=json.loads(review.read_text())['scenes'];diff=[x['id'] for x in data if x['id'] not in expected or any(expected[x['id']].get(k)!=x.get(k) for k in ['imagePath','sha256','hotspotSha256','objectPosition','descriptionSha256'])]
   diff+=list(set(expected)-{x['id'] for x in data})
   check('scene:reviewed-art-hotspot-pairs-not-drifted',not diff,diff)
  reset();ev("addItem('spell crystal');showItemInspection('spell crystal')");page.screenshot(path=str(OUT/'inspection-mobile.png'),full_page=True)
  ev("document.getElementById('item-inspection-dialog').close();renderAll()")
  page.wait_for_timeout(120);page.screenshot(path=str(OUT/'play-mobile.png'),full_page=True)
  page.set_viewport_size({'width':844,'height':390});ev('settleViewportAfterOrientation()');page.wait_for_timeout(800)
  check('layout:landscape-no-horizontal-overflow',ev('document.documentElement.scrollWidth<=innerWidth+1'))
  page.screenshot(path=str(OUT/'play-landscape.png'),full_page=True)
  check('runtime:no-unexpected-missing-assets',not missing,missing)
  check('runtime:no-page-errors',not errors,errors)
 except Exception:check('suite:unhandled-error',False,traceback.format_exc());print(traceback.format_exc())
 finally:
  b.close();summary=dict(suite='consistency',fixture='Chromium, real local asset responses, Map-backed storage; not Safari/PWA certification',passed=sum(x['passed'] for x in results),total=len(results),results=results)
  (OUT/'consistency.json').write_text(json.dumps(summary,indent=2));print(f'{summary["passed"]}/{summary["total"]} passed')
  sys.exit(0 if summary['passed']==summary['total'] else 1)
