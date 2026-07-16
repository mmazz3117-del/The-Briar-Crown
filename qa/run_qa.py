#!/usr/bin/env python3
from pathlib import Path
import json, re, sys, hashlib
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/mnt/data/briar1716_work')
CONTRACT=json.loads((Path(__file__).parent/'contracts.json').read_text())
results=[]

def check(name, ok, detail=''):
    results.append((name,bool(ok),detail))
    if not ok:
        print('FAIL',name,detail)
    else:
        print('PASS',name,detail)

# Static package checks
index=(ROOT/'index.html').read_text()
manifest=json.loads((ROOT/'manifest.json').read_text())
sw=(ROOT/'service-worker.js').read_text()
check('version:index', '1.7.1.6' in index)
check('version:manifest', manifest.get('version')=='1.7.1.6')
check('version:cache', 'briar-crown-v1.7.1.6' in sw)
check('asset:satchel', (ROOT/'assets/ui/satchel.png').exists())
check('menu:scene-test-button-restored', 'id="scene-tour-btn"' in index)

# Every referenced local scene exists
refs=sorted(set(re.findall(r'assets/scenes/[A-Za-z0-9._-]+',index)))
missing=[r for r in refs if not (ROOT/r).exists()]
check('assets:all-scene-references-exist', not missing, ', '.join(missing))

# Image technical quality gates
for name in ['forge-lane.webp','hidden-passage-v2.webp','hidden-alcove.webp','hidden-alcove-coins.webp']:
    p=ROOT/'assets/scenes'/name
    im=Image.open(p).convert('RGB')
    check(f'image:{name}:minimum-resolution', im.width>=900 and im.height>=700, f'{im.size}')
    # No wide uniform matte/letterbox bands: top/bottom strips should have visible texture.
    top=im.crop((0,0,im.width,max(10,im.height//12)))
    bot=im.crop((0,im.height-max(10,im.height//12),im.width,im.height))
    v1=sum(ImageStat.Stat(top).var)/3
    v2=sum(ImageStat.Stat(bot).var)/3
    check(f'image:{name}:no-flat-letterbox', v1>35 and v2>35, f'edge variance {v1:.1f}/{v2:.1f}')

html=index.replace('<head>','<head><base href="file://'+str(ROOT)+'/">',1)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--allow-file-access-from-files'])
    page=browser.new_page(viewport={'width':430,'height':932})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load')
    check('browser:no-page-errors', not errors, '; '.join(errors))
    check('ui:map-top-button', page.locator('#map-btn .label').inner_text().strip()=='Map')
    check('ui:satchel-label', page.locator('#backpack-btn small').inner_text().strip()=='Satchel')
    viewport_meta=page.locator('meta[name=viewport]').get_attribute('content') or ''
    check('zoom:browser-pinch-enabled','user-scalable=yes' in viewport_meta and 'maximum-scale=5' in viewport_meta,viewport_meta)
    check('zoom:map-pinch-enabled','touch-action: pan-x pan-y pinch-zoom' in index)

    # Helper fresh hero state
    def reset(room='square'):
        page.evaluate("""room => {
          state=initialState();
          state.player={name:'QA Hero',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};
          state.room=room; state.visited=[room]; state.log=[]; restoreDynamicExits();
          document.getElementById('start-overlay').hidden=true;
          renderAll();
        }""",room)

    # Tavern staged discovery
    reset('tavern')
    acts=page.evaluate('currentActions().map(normalize)')
    for a in CONTRACT['scenes']['tavern']['fresh_forbidden']:
        check(f'contract:tavern:fresh-forbids:{a}',a not in acts,str(acts))
    labels=page.evaluate('currentHotspots().map(h=>h.label)')
    check('contract:tavern:scuffed-floor-first','Scuffed Floor' in labels and 'Cellar Hatch' not in labels,str(labels))
    page.evaluate("processCommand('look at cellar door')")
    check('contract:tavern:hatch-discovered',page.evaluate('state.flags.hatchDiscoveryConfirmed') is True)
    acts=page.evaluate('currentActions().map(normalize)')
    check('contract:tavern:ask-after-discovery','ask innkeeper about cellar' in acts,str(acts))
    check('contract:tavern:no-go-down-before-open','go down' not in acts,str(acts))
    page.evaluate("state.flags.cellarUnlocked=true; processCommand('open cellar hatch')")
    acts=page.evaluate('currentActions().map(normalize)')
    check('contract:tavern:go-down-after-open','go down' in acts,str(acts))

    # Persistent navigation remains visible at room entry and after selecting an object.
    reset('tavern')
    default_labels=page.evaluate("defaultSceneActions().map(quickActionLabel)")
    check('navigation:tavern-exit-default','Go Outside' in default_labels,str(default_labels))
    page.evaluate("""() => {
      const h=currentHotspots().find(x=>x.label==='Fireplace');
      selectedHotspotContext={hotspot:h,room:state.room,view:currentView()}; renderQuickActions();
    }""")
    selected_labels=page.locator('#quick-actions button').all_inner_texts()
    check('navigation:tavern-exit-selected',any('Go Outside' in x for x in selected_labels),str(selected_labels))

    reset('tavernCellar')
    page.evaluate("""() => {
      const h=currentHotspots().find(x=>x.label==='Barrels');
      selectedHotspotContext={hotspot:h,room:state.room,view:currentView()}; renderQuickActions();
    }""")
    cellar_labels=page.locator('#quick-actions button').all_inner_texts()
    check('navigation:cellar-up-selected',any('Go Up' in x for x in cellar_labels),str(cellar_labels))

    # Fireplace staged treasure
    reset('tavern')
    page.evaluate("processCommand('look at fireplace')")
    acts=page.evaluate('currentActions().map(normalize)')
    check('contract:fireplace:move-button','move brick' in acts,str(acts))
    gold_before=page.evaluate('state.gold')
    page.evaluate("processCommand('move brick')")
    acts=page.evaluate('currentActions().map(normalize)')
    check('contract:fireplace:collect-button','take treasure' in acts,str(acts))
    check('contract:fireplace:not-auto-collected',page.evaluate('state.gold')==gold_before and not page.evaluate("has('tarnished locket')"))
    page.evaluate("processCommand('take treasure')")
    check('contract:fireplace:gold-collected',page.evaluate('state.gold')==gold_before+6)
    check('contract:fireplace:locket-collected',page.evaluate("has('tarnished locket')") is True)

    # Apothecary default action contract
    reset('apothecary')
    defaults=page.evaluate('defaultSceneActions().map(normalize)')
    for a in CONTRACT['scenes']['apothecary']['default_required']:
        check(f'contract:apothecary:default:{a}',a in defaults,str(defaults))

    # Shield equipment contract
    reset('forgeLane')
    page.evaluate("addItem('wooden shield'); renderAll(); showInventory()")
    check('equipment:shield-equip-button',page.locator('[data-equip-item="wooden shield"]').count()==1)
    page.locator('[data-equip-item="wooden shield"]').click()
    check('equipment:shield-slot',page.evaluate('state.equipment.shield')=='wooden shield')
    check('equipment:shield-defense',page.evaluate('totalDefense()')==1)

    # Map direct button and production menu
    page.locator('#map-btn').click()
    check('navigation:map-opens-direct',page.locator('#map-dialog').evaluate('(d)=>d.open'))
    page.locator('#map-dialog [data-close]').click()
    page.locator('#menu-btn').click()
    menu_text=page.locator('#menu-dialog').inner_text()
    check('navigation:menu-has-quest-book','Quest Book' in menu_text)
    check('navigation:menu-has-scene-test','Scene Test' in menu_text)
    page.locator('#scene-tour-btn').click()
    check('navigation:scene-test-opens',page.locator('#scene-dialog').evaluate('(d)=>d.open'))
    page.locator('#scene-dialog [data-close]').click()

    # Grave hotspot mobile geometry
    reset('chapelYard')
    grave=page.evaluate("currentHotspots().find(h=>h.label==='Graves')")
    check('hotspot:graves-width',grave and grave['w']>=38,str(grave))
    check('hotspot:graves-lower-alignment',grave and grave['y']>=66,str(grave))


    # Save migration: contradictory pre-contract hatch flags are sanitized.
    page.evaluate("""() => {
      state=initialState(); state.schemaVersion=1714; state.flags.hatchNoticed=true; state.flags.hatchDiscoveryConfirmed=false;
      state.flags.cellarUnlocked=true; state.flags.tavernCellarOpen=true; state.visited=['tavern']; migrateState(); restoreDynamicExits();
    }""")
    check('migration:premature-hatch-cleared',page.evaluate('!state.flags.cellarUnlocked && !state.flags.tavernCellarOpen'))
    check('migration:schema-updated',page.evaluate('state.schemaVersion')==1715)
    check('migration:no-go-down-after-sanitize','go down' not in page.evaluate('currentActions().map(normalize)'))

    page.evaluate("""() => {
      state=initialState(); state.schemaVersion=1714; state.room='tavernCellar'; state.visited=['tavern','tavernCellar'];
      state.flags.hatchNoticed=true; state.flags.cellarUnlocked=true; state.flags.tavernCellarOpen=true; migrateState(); restoreDynamicExits();
    }""")
    check('migration:real-cellar-progress-preserved',page.evaluate('state.flags.hatchDiscoveryConfirmed && state.flags.tavernCellarOpen'))

    # Hotspot and action structural contracts across all rooms/views.
    bad_spots=page.evaluate("""() => {
      const bad=[];
      for (const [id,r] of Object.entries(rooms)) for (const h of (r.hotspots||[])) {
        if (!h.command || h.x<0 || h.y<0 || h.x>100 || h.y>100 || (h.w||0)<=0 || (h.h||0)<=0 || h.x+(h.w||0)>115 || h.y+(h.h||0)>115) bad.push(id+':'+h.label);
      }
      return bad;
    }""")
    check('hotspots:valid-bounds-and-actions',not bad_spots,str(bad_spots))

    duplicate_rooms=page.evaluate("""() => {
      const original=state; const bad=[];
      for (const id of Object.keys(rooms)) {
        state=initialState(); state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats}; state.room=id; restoreDynamicExits();
        const keys=currentActions().map(canonicalActionKey); if (new Set(keys).size!==keys.length) bad.push(id);
      }
      state=original; restoreDynamicExits(); renderAll(); return bad;
    }""")
    check('actions:no-duplicates-across-rooms',not duplicate_rooms,str(duplicate_rooms))

    # Core graph exits
    no_exit=page.evaluate("Object.entries(rooms).filter(([id,r])=>!Object.keys(r.exits||{}).length).map(([id])=>id)")
    check('graph:all-rooms-have-exit',not no_exit,str(no_exit))

    # Screenshot basic mobile frame with game visible
    reset('apothecary')
    page.screenshot(path=str(ROOT/'qa-mobile-apothecary.png'),full_page=True)
    browser.close()

passed=sum(ok for _,ok,_ in results); total=len(results)
report=[f'The Briar Crown v1.7.1.6 QA Report',f'Passed: {passed}/{total}','']
for name,ok,detail in results:
    report.append(f'[{"PASS" if ok else "FAIL"}] {name}' + (f' — {detail}' if detail else ''))
(ROOT/'QA_REPORT_v1.7.1.6.txt').write_text('\n'.join(report)+'\n')
print(f'\nRESULT {passed}/{total}')
if passed!=total: sys.exit(1)
