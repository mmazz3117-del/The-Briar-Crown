#!/usr/bin/env python3
"""Player-entry-point regressions for v1.7.8.0.
Chromium document fixture + deterministic storage. NOT an iOS/offline test.
Usage: python qa/run_stabilization.py [game root] [results directory]
"""
from pathlib import Path
import json, sys, shutil, traceback
from playwright.sync_api import sync_playwright
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'qa-results'
OUT.mkdir(parents=True, exist_ok=True)
results=[]
def check(name, ok, detail=None):
    results.append({'test':name,'passed':bool(ok),'detail':detail})
    print(('PASS ' if ok else 'FAIL ')+name, flush=True)

def run():
 with sync_playwright() as p:
  args={'headless':True,'args':['--no-sandbox','--allow-file-access-from-files']}
  exe=shutil.which('chromium') or shutil.which('chromium-browser')
  if exe: args['executable_path']=exe
  b=p.chromium.launch(**args)
  page=b.new_page(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
  page.set_default_timeout(3000)
  errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
  page.on('dialog', lambda d: d.accept())
  html=(ROOT/'index.html').read_text()
  shim="""<script>window.qaStore=new Map([['briar-crown-music-enabled','false']]);Object.defineProperty(window,'localStorage',{value:{getItem:k=>qaStore.get(k)??null,setItem:(k,v)=>qaStore.set(k,String(v)),removeItem:k=>qaStore.delete(k)}});</script>"""
  html=html.replace('<head>',f'<head><base href="file://{ROOT}/">'+shim,1)
  page.set_content(html,wait_until='load')
  ev=page.evaluate
  def reset(room='square',hero='ranger'):
   ev("""([room,key])=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());resetCombatPresentation();state=initialState();state.player={name:'QA',classKey:key,className:heroClasses[key].name,stats:{...heroClasses[key].stats}};Object.assign(state.skills,classSkillStarts[key]);state.flags.classSkillStartApplied=true;state.room=room;restoreDynamicExits();document.getElementById('start-overlay').hidden=true;selectedHotspotContext=null;Math.random=()=>.2;renderAll();}""",[room,hero])
  def cmd(c): ev('(c)=>processCommand(c)',c)
  check('boot:no-script-errors',not errors,errors[:])
  # Correct item/target pairs through every public dispatch boundary.
  pairs=[('cottage','silver key','trapdoor','trapdoorUnlocked'),('chapel','fairy coin','statue','cryptOpen'),('crypt','silver token','reliquary','reliquaryOpen'),('moonfen','ferry crank','winch','ferryRepaired'),('moonwell','iron hook','well','shardTaken'),('moonwell','sun sigil','cage','fairyFreed'),('castleGate','crown shard','gate','gateShardReady'),('square','flint','lantern','lanternLit')]
  for room,item,target,flag in pairs:
   for mode in ['typed','quick','give','direct-titlecase','natural']:
    reset(room);ev("item=>{addItem(item);addItem('lantern');state.flags.rugMoved=true;}",item)
    if mode=='typed':cmd(f'use {item} on {target}')
    elif mode=='quick':ev('(c)=>executeQuickAction(c)',f'use {item} on {target}')
    elif mode=='give':cmd(f'give {item} to {target}')
    elif mode=='natural':cmd(f'Please use the {item} on the {target}.')
    else:ev('([i,t])=>useItem(i,t)',[item.title(),target.title()])
    detail=ev('f=>({success:!!state.flags[f],log:state.log.slice(-2)})',flag)
    check(f'puzzle:{item}:{mode}',detail['success'],detail)
  reset('cottage');ev("addItem('silver key');state.flags.rugMoved=true")
  cmd('use silver key on fireplace')
  check('puzzle:wrong-target-does-not-unlock',not ev('state.flags.trapdoorUnlocked'))
  # Reset via actual New Adventure entry point, without calling restore after it.
  reset();ev("Object.assign(state.flags,{trapdoorOpen:true,cryptOpen:true,hatchDiscoveryConfirmed:true,tavernCellarOpen:true,cellarPassageRevealed:true,ferryRepaired:true,ending:'dawn'});restoreDynamicExits();selectedEquipmentItem='iron dagger';selectedHotspotContext={room:'square',hotspot:{label:'Old selection'}}")
  ev("async()=>{selectedHeroClass='ranger';await beginAdventure()}")
  stale=ev("Object.fromEntries([['cottage','down'],['chapel','down'],['tavern','down'],['tavernCellar','east'],['moonfen','east']].filter(([r,d])=>rooms[r].exits[d]).map(([r,d])=>[r,rooms[r].exits[d]]))")
  check('new-adventure:no-inherited-exits',not stale,stale)
  ev("state.room='moonfen';renderAll()");cmd('east')
  check('new-adventure:ferry-actually-blocked',ev("state.room==='moonfen'&&!state.flags.ferryRepaired&&!has('ferry crank')"))
  check('new-adventure:clear-ui-selections',ev('selectedEquipmentItem===null&&selectedHotspotContext===null'))
  # Consumable effects through real inspection/satchel clicks and typed commands.
  heals={'healing herbs':5,'minor healing tonic':6,'field bandage':4,"traveler's poultice":8,'healing salve':8,'healing potion':20}
  for item,heal in heals.items():
   for mode in ['typed','inspection','satchel','combat-button','combat-typed']:
    for hp in [6,20]:
     reset();ev('([i,h])=>{addItem(i,2);state.health=h}',[item,hp])
     if mode.startswith('combat'):
      ev("startCombat('thornHound');beginCombatFromEncounter()")
      if mode=='combat-typed':cmd('use '+item)
      else:
       btn=page.locator('[data-combat-action="item"]')
       if btn.is_enabled():btn.click()
     elif mode=='inspection':
      ev('(i)=>showItemInspection(i)',item)
      btn=page.locator('[data-inspection-use]')
      if btn.is_enabled():btn.click()
     elif mode=='satchel':
      ev('showInventory()');btn=page.locator('[data-use-item]').filter(has_text='Use').first
      if btn.count() and btn.is_enabled():btn.click()
     else:cmd('use '+item)
     page.wait_for_timeout(35)
     observed=ev('i=>({health:state.health,qty:itemQty(i),phase:state.combat?.phase,log:state.log.slice(-2)})',item)
     expected=min(20,hp+heal) if hp<20 else 20
     ok=observed['health']==expected and observed['qty']==(1 if hp<20 else 2)
     if mode.startswith('combat'):ok=ok and observed.get('phase')==('enemy-ready' if hp<20 else 'player')
     check(f'healing:{item}:{mode}:hp{hp}',ok,observed)
  # Zero is a real value, not a request to substitute maximum HP/focus.
  reset();ev("state.focus=0;addItem('stamina draught',2)");cmd('use stamina draught')
  check('consumable:focus-zero',ev("state.focus===8&&itemQty('stamina draught')===1"))
  reset();ev("state.focus=10;addItem('stamina draught',2)");cmd('use stamina draught')
  check('consumable:full-focus-keeps-item',ev("itemQty('stamina draught')===2"))
  reset();ev("addItem('antidote',2)");cmd('use antidote')
  check('consumable:no-poison-keeps-antidote',ev("itemQty('antidote')===2"))
  reset();ev("state.flags.poisoned=true;addItem('antidote',2)");cmd('use antidote')
  check('consumable:antidote-clears-poison',ev("state.flags.poisoned===false&&itemQty('antidote')===1"))
  # Purchased and class-starting tools must resolve to the same usable inventory id.
  reset('apothecary');cmd('buy lockpick');ev("state.room='tavern';state.flags.hatchDiscoveryConfirmed=true;Math.random=()=>.99");cmd('pick cellar lock')
  check('lock:shop-tool-works',ev('state.flags.cellarUnlocked'),ev('state.log.slice(-3)'))
  totals=[]
  for equipped in [False,True]:
   reset('tavern','rogue');ev("addItem('lockpicks');state.flags.hatchDiscoveryConfirmed=true;Math.random=()=>.2")
   if equipped:ev("equipItem('lockpicks')")
   cmd('pick cellar lock');totals.append(ev("state.log.filter(l=>/Lockpicking check/.test(l.text)).at(-1)?.text"))
  import re
  nums=[re.search(r'd20 (\d+) \+ (\d+) = (\d+)',s or '') for s in totals]
  check('lock:equipped-bonus-exactly-one',all(nums) and int(nums[1][2])-int(nums[0][2])==1,totals)
  # Information-only requests may reveal authored clues, not move objects or award loot.
  info=[('tavernCellar','flagstone',['cellarFlagstoneAttempted','cellarFlagstoneLooted']),('secretAlcove','cracked wall',['alcoveWallAttempted','alcoveWallLooted']),('thornHedgePass','abandoned pack',['abandonedPackSearched']),('secretAlcove','loose stone',['tunnelCoinsFound','tunnelCoinsTaken']),('crypt','stone coffin',['cryptCoffinOpened','cryptSkeletonDefeated'])]
  for room,obj,flags in info:
   for verb in ['look at','examine','inspect','read']:
    reset(room);before=ev('({inventory:state.inventory,itemCounts:state.itemCounts,gold:state.gold,health:state.health})');cmd(verb+' '+obj)
    after=ev('(fs)=>({inventory:state.inventory,itemCounts:state.itemCounts,gold:state.gold,health:state.health,changed:fs.filter(f=>state.flags[f]),combat:!!state.combat||!!state.pendingEncounter})',flags)
    ok=all(after[k]==v for k,v in before.items()) and not after['changed'] and not after['combat']
    check(f'information:{room}:{obj}:{verb}',ok,after)
  reset('thornHedgePass');cmd('search abandoned pack')
  check('information:explicit-search-still-loots',ev("state.flags.abandonedPackSearched&&has('healing herbs')"))
  reset('secretAlcove');cmd('search loose stone')
  check('information:explicit-stone-search-still-reveals',ev('state.flags.tunnelCoinsFound'))
  # All known owned items should use the same inspection UI, without applying effects.
  reset();items=ev('Array.from(new Set([...Object.keys(itemInfo),...Object.keys(equipmentInfo),...Object.keys(apothecaryShop),...Object.keys(forgeShop)]))')
  for item in items:
   reset();ev('i=>addItem(i)',item);cmd('examine '+item)
   check('inspection:typed:'+item,ev("i=>document.getElementById('item-inspection-dialog').open&&itemQty(i)===1&&state.health===20&&state.gold===20",item))
  # Quantity migration: counts are authoritative, inventory membership isn't another item.
  fixtures=[(['healing herb'],{'healing herb':2},2),(['healing herb'],{},1),(['healing herbs'],{'healing herbs':2},2),(['healing herb','healing herbs'],{'healing herb':2,'healing herbs':3},5)]
  for inventory,counts,expected in fixtures:
   reset();ev('([inv,counts])=>{state.inventory=inv;state.itemCounts=counts;migrateState()}',[inventory,counts])
   q1=ev("itemQty('healing herbs')");ev('migrateState()');q2=ev("itemQty('healing herbs')")
   check('migration:herbs:'+json.dumps(counts),q1==expected and q2==expected,{'first':q1,'second':q2,'expected':expected})
  reset();ev("state.inventory=['lockpick'];state.itemCounts={'lockpick':2};state.equipment={belt:'lockpick'};migrateState()")
  check('migration:lockpick-equipment',ev("has('lockpicks')&&itemQty('lockpicks')===2&&state.equipment.belt==='lockpicks'"))
  # Save failure and corrupt restore must not destroy last-good progress.
  reset();ev('saveGame()')
  check('save:success-is-real',ev("JSON.parse(storageGet(SAVE_KEY)).room===state.room&&state.log.at(-1).text.includes('saved to this device')"))
  old=ev('storageGet(SAVE_KEY)');ev("window.qaOldSet=localStorage.setItem;localStorage.setItem=()=>{throw new DOMException('Quota test','QuotaExceededError')};saveGame()")
  messages=ev('state.log.slice(-2).map(x=>x.text).join(" ")')
  check('save:failure-is-not-success',not ev("state.log.at(-1).text.includes('Game saved to this device.')"),messages)
  check('save:failure-retains-last-good',ev('storageGet(SAVE_KEY)')==old)
  ev('localStorage.setItem=window.qaOldSet')
  reset();ev("state.gold=37;addItem('silver key');storageSet(SAVE_KEY,'{corrupt');loadGame()")
  check('save:corrupt-json-keeps-live-state',ev("state.gold===37&&has('silver key')"))
  reset();ev("state.gold=37;addItem('silver key');storageSet(SAVE_KEY,'null');loadGame()")
  check('save:invalid-shape-keeps-live-state',ev("!!state&&state.gold===37&&has('silver key')"))
  reset();ev("state.pendingLoot={enemyId:'thornHound',gold:3};state.pendingEncounter='thornHound';state.flags.ferryRepaired=true;state.flags.tunnelCoinsTaken=true;addItem('crown shard');state.gold=999;inputEl.focus();selectedHeroClass='wizard'")
  ev('beginAdventure()')
  check('new-adventure:clears-rewards-combat-inventory',ev("!state.pendingLoot&&!state.pendingEncounter&&!state.combat&&!has('crown shard')&&state.gold===20&&!state.flags.ferryRepaired&&!state.flags.tunnelCoinsTaken"))
  check('new-adventure:clears-keyboard',ev("document.activeElement!==inputEl&&!document.body.classList.contains('keyboard-open')"))
  reset();ev('saveGame();window.qaSilentOldSet=localStorage.setItem;localStorage.setItem=()=>{};state.gold=33;saveGame()')
  check('save:silent-write-failure-detected',ev("!lastSaveResult.ok&&JSON.parse(storageGet(SAVE_KEY)).gold===20"))
  ev('localStorage.setItem=window.qaSilentOldSet')
  reset();ev("state.gold=31;window.qaTooNew=JSON.stringify({...state,schemaVersion:9999});window.qaRestoreResult=restoreSavedText(qaTooNew)")
  check('save:newer-schema-is-not-destructively-loaded',ev("!qaRestoreResult.ok&&state.gold===31"))
  reset();cmd('examine nonexistent crown potion')
  check('inspection:unknown-item-not-invented',ev("state.inventory.length===0&&!document.getElementById('item-inspection-dialog').open"))
  check('runtime:no-page-errors',not errors,errors)
  b.close()

try: run()
except Exception:
 check('suite:unhandled-error',False,traceback.format_exc());print(traceback.format_exc())
finally:
 summary={'suite':'stabilization','fixture':'Chromium document + Map-backed storage; no real Safari/PWA certification','passed':sum(r['passed'] for r in results),'total':len(results),'results':results}
 (OUT/'stabilization.json').write_text(json.dumps(summary,indent=2))
 (OUT/'stabilization.txt').write_text('\n'.join(('PASS ' if r['passed'] else 'FAIL ')+r['test'] for r in results)+f'\n{summary["passed"]}/{summary["total"]} passed\n')
 print(f'{summary["passed"]}/{summary["total"]} passed')
 sys.exit(0 if summary['passed']==summary['total'] else 1)
