#!/usr/bin/env python3
"""v1.7.9.2.4 visual-polish smoke tests.
Uses real packaged assets and DOM click delivery in Chromium. This validates scene
bindings, state artwork, hotspot delivery, item-art loading, and responsive layout;
it does not certify Safari/Home-Screen persistence or live service-worker install.
"""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,mimetypes,shutil,sys,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'qa-results';OUT.mkdir(parents=True,exist_ok=True)
results=[]
def check(name,ok,detail=None):
    results.append({'test':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
with sync_playwright() as p:
    launch={'headless':True,'args':['--no-sandbox']}
    if shutil.which('chromium'):launch['executable_path']=shutil.which('chromium')
    browser=p.chromium.launch(**launch);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page.set_default_timeout(5000);errors=[];missing=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
    def serve(route):
        name=unquote(urlsplit(route.request.url).path.lstrip('/'));path=(ROOT/name).resolve()
        if path.is_relative_to(ROOT) and path.is_file():route.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream',headers={'Access-Control-Allow-Origin':'*'})
        else:missing.append(name);route.fulfill(status=404,body='Not found')
    page.route('https://briar-crown.test/**',serve)
    shim="""<script>window.qaStore=new Map([['briar-crown-music-enabled','false']]);Object.defineProperty(window,'localStorage',{value:{getItem:k=>qaStore.get(k)??null,setItem:(k,v)=>qaStore.set(k,String(v)),removeItem:k=>qaStore.delete(k)}});</script>"""
    html=(ROOT/'index.html').read_text().replace('<head>','<head><base href="https://briar-crown.test/">'+shim,1)
    page.set_content(html,wait_until='load');ev=page.evaluate
    def reset(room='square',view='center'):
        ev("""({room,view})=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());state=initialState();state.room=room;state.view=view;resetAdventurePresentation();restoreDynamicExits();state.flags.tutorialSceneTapComplete=true;state.flags.tutorialCommandComplete=true;document.getElementById('start-overlay').hidden=true;Math.random=()=>.95;renderAll();window.scrollTo(0,0)}""",{'room':room,'view':view})
        page.wait_for_function('pendingSceneKey==="" && !!document.querySelector(".scene-image")?.naturalWidth')
    def tap_landmark(group,x,y,labels):
        ev('selectedHotspotContext=null')
        pt=ev("""([x,y])=>{const r=hotspotsEl.getBoundingClientRect();const px=r.left+r.width*x/100,py=r.top+r.height*y/100;return {x:px,y:py,hit:document.elementFromPoint(px,py)?.closest('.hotspot')?.dataset.label||null}}""",[x,y])
        page.mouse.click(pt['x'],pt['y']);page.wait_for_timeout(70);selected=ev('selectedHotspotContext?.hotspot?.label||null')
        check(group,selected in labels and pt['hit'] in labels,{'expected':labels,'hit':pt['hit'],'selected':selected})
    try:
        # Distinct coordinated tavern views: asset, description and one hand-reviewed landmark each.
        tavern={
          'center':('tavern-interior-v17922.webp',51,82,['Scuffed Floor','Cellar Hatch']),
          'north':('tavern-north-v17923.webp',84,45,['Innkeeper']),
          'east':('tavern-east-v17923.webp',50,40,['Stairs']),
          'west':('tavern-west-v17923.webp',50,58,['Fireplace']),
          'south':('tavern-south-v17923.webp',6,34,['Tavern Door'])}
        for view,(fn,x,y,labels) in tavern.items():
            reset('tavern',view);check(f'tavern:{view}:asset',ev('currentScenePresentation().imagePath').endswith(fn),ev('currentScenePresentation().imagePath'))
            tap_landmark(f'tavern:{view}:landmark',x,y,labels)
            check(f'tavern:{view}:exit-available',ev("persistentNavigationActions().includes('go outside')"))
        # Dedicated exterior focus state at the tavern threshold uses the approved exterior art crop.
        reset('tavernDoor');check('tavernDoor:focus-asset',ev('currentScenePresentation().imagePath').endswith('tavern-door-v17924.webp'),ev('currentScenePresentation().imagePath'))
        tap_landmark('tavernDoor:door-landmark',48,60,['Tavern Door'])
        check('tavernDoor:return-exit',ev("persistentNavigationActions().includes('south') || currentActions().includes('go south')"))
        # Hatch geometry is stable in the two views that expose the floor clue.
        for view in ['center','east']:
            reset('tavern',view);before=ev("currentHotspots().find(h=>/Scuffed Floor|Cellar Hatch/.test(h.label))")
            ev("state.flags.hatchDiscoveryConfirmed=true;state.flags.cellarUnlocked=true;state.flags.tavernCellarOpen=true;restoreDynamicExits();renderAll()")
            after=ev("currentHotspots().find(h=>/Scuffed Floor|Cellar Hatch/.test(h.label))")
            check(f'tavern:{view}:hatch-does-not-jump',bool(before and after) and all(before[k]==after[k] for k in ['x','y','w','h']),{'before':before,'after':after})
        # Cellar retains clean base art; a live state badge confirms the passage is revealed, then the route works both ways.
        reset('tavernCellar');fresh=ev('currentScenePresentation().imagePath')
        ev("processCommand('look at wine rack')");ev("processCommand('move wine rack')");page.wait_for_function('pendingSceneKey===""')
        opened=ev('currentScenePresentation().imagePath')
        badge=ev("document.getElementById('scene-state-badge')?.textContent||''")
        check('cellar:passage-has-visible-state',fresh==opened and 'passage revealed' in badge.lower(),{'fresh':fresh,'opened':opened,'badge':badge})
        check('cellar:one-passage-target',ev("currentHotspots().filter(h=>/Wine Rack|Hidden Passage/.test(h.label)).length===1"))
        ev("processCommand('enter hidden passage')");check('cellar:enter-tunnel',ev("state.room==='secretTunnel'"));ev("processCommand('go west')");check('cellar:return-preserves-open-state',ev("state.room==='tavernCellar'&&state.flags.cellarPassageRevealed"))
        # Major solved/collected objects use explicit visual states where dedicated art is clean;
        # cottage/crypt use polished live state badges rather than composited placeholder art.
        reset('cottage');a=ev('currentScenePresentation().imagePath');ev('state.flags.rugMoved=true;renderAll()');b=ev('currentScenePresentation().imagePath');bb=ev("document.getElementById('scene-state-badge')?.textContent||''");ev('state.flags.trapdoorOpen=true;renderAll()');c=ev('currentScenePresentation().imagePath');bc=ev("document.getElementById('scene-state-badge')?.textContent||''")
        check('state-art:cottage-rug-and-trapdoor',a==b==c and 'trapdoor revealed' in bb.lower() and 'trapdoor open' in bc.lower(),{'paths':[a,b,c],'badges':[bb,bc]})
        reset('hutInterior');a=ev('currentScenePresentation().imagePath');ev('state.flags.coinTaken=true;renderAll()');b=ev('currentScenePresentation().imagePath');check('state-art:fairy-coin-collected',a!=b and b.endswith('hut-interior-collected-v1790.webp'),[a,b])
        reset('secretAlcove');ev('state.flags.tunnelCoinsFound=true;renderAll()');a=ev('currentScenePresentation().imagePath');ev('state.flags.tunnelCoinsTaken=true;renderAll()');b=ev('currentScenePresentation().imagePath');check('state-art:alcove-empty-after-coins',a!=b and b.endswith('collapsed-alcove-empty-v1790.webp'),[a,b])
        reset('moonwell');a=ev('currentScenePresentation().imagePath');ev('state.flags.fairyFreed=true;renderAll()');b=ev('currentScenePresentation().imagePath');check('state-art:fairy-freed',a!=b and b.endswith('moonwell-free-v1790.webp'),[a,b])
        reset('crypt');a=ev('currentScenePresentation().imagePath');ev('state.flags.reliquaryOpen=true;renderAll()');b=ev('currentScenePresentation().imagePath');bb=ev("document.getElementById('scene-state-badge')?.textContent||''");ev('state.flags.cryptSkeletonDefeated=true;renderAll()');c=ev('currentScenePresentation().imagePath');bc=ev("document.getElementById('scene-state-badge')?.textContent||''");check('state-art:crypt-progress',a==b==c and 'reliquary opened' in bb.lower() and 'stone coffin opened' in bc.lower(),{'paths':[a,b,c],'badges':[bb,bc]})
        # Every item now resolves to package artwork and a representative card actually loads it.
        registry=json.loads((ROOT/'assets/items/manifest.json').read_text());check('item-art:all-41-custom',len(registry['items'])==41 and all(v.get('art') for v in registry['items'].values()))
        reset();ev('loadItemArtworkManifest()');page.wait_for_timeout(200);ev("addItem('spell crystal');showItemInspection('spell crystal')");page.wait_for_function('document.querySelector(".inspection-art").dataset.artStatus==="custom-art"');check('item-art:inspection-loads-custom',True)
        # Layout remains usable in portrait and landscape.
        for width,height in [(390,844),(844,390)]:
            page.set_viewport_size({'width':width,'height':height});ev('settleViewportAfterOrientation()');page.wait_for_timeout(600);reset('tavern','north')
            rect=ev("""()=>{const s=document.querySelector('.scene-shell').getBoundingClientRect(),c=document.querySelector('.controls').getBoundingClientRect(),l=document.querySelector('#log').getBoundingClientRect();return {s:{left:s.left,right:s.right,top:s.top,bottom:s.bottom},c:{left:c.left,right:c.right,top:c.top,bottom:c.bottom},log:{width:l.width,height:l.height},iw:innerWidth,ih:innerHeight,sw:document.documentElement.scrollWidth}}""")
            check(f'layout:{width}x{height}:no-horizontal-overflow',rect['sw']<=width+1,rect)
            check(f'layout:{width}x{height}:scene-visible',rect['s']['left']>=-1 and rect['s']['right']<=width+1 and rect['s']['top']>=-1 and rect['s']['bottom']<=height+1,rect)
        page.screenshot(path=str(OUT/'v1791-tavern-north-mobile.png'),full_page=True)
        # Progressed world -> new adventure returns to baseline visuals and routes.
        reset('tavernCellar');ev("state.flags.cellarPassageRevealed=true;state.flags.tavernCellarOpen=true;state.flags.hatchDiscoveryConfirmed=true;restoreDynamicExits();selectedHeroClass='knight';beginAdventure()")
        check('new-adventure:visual-world-reset',ev("!state.flags.cellarPassageRevealed&&!rooms.tavernCellar.exits.east&&!rooms.tavern.exits.down"))
        check('runtime:no-unexpected-missing-assets',not missing,missing);check('runtime:no-page-errors',not errors,errors)
    except Exception:
        check('suite:unhandled-error',False,traceback.format_exc());print(traceback.format_exc())
    finally:
        browser.close();summary={'suite':'visual-completion-smoke','fixture':'Chromium + actual package files; not Safari/PWA certification','passed':sum(r['passed'] for r in results),'total':len(results),'results':results};(OUT/'cleanup-smoke.json').write_text(json.dumps(summary,indent=2));print(f"{summary['passed']}/{summary['total']} passed");sys.exit(0 if summary['passed']==summary['total'] else 1)
