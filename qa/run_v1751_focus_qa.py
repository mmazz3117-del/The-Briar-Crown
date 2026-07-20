#!/usr/bin/env python3
from pathlib import Path
import shutil, sys
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
index = (ROOT / "index.html").read_text()
html = index.replace("<head>", f'<head><base href="file://{ROOT}/">', 1)
results = []

def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS" if ok else "FAIL"), name, detail)

with sync_playwright() as pw:
    launch_args = {"headless": True, "args": ["--no-sandbox", "--allow-file-access-from-files"]}
    executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if executable:
        launch_args["executable_path"] = executable
    browser = pw.chromium.launch(**launch_args)
    page = browser.new_page(viewport={"width": 430, "height": 932})
    page.set_default_timeout(5000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(html, wait_until="load")
    page.evaluate("""() => {
      state=initialState();
      state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};
      state.log=[];
      document.getElementById('start-overlay').hidden=true;
      actionsPanelExpanded=false;
      sceneNavigationVisible=false;
      renderAll();
    }""")

    check("browser:no-errors", not errors, ";".join(errors))
    check("actions:collapsed", page.evaluate("document.getElementById('quick-actions').classList.contains('is-hidden')"))
    check("navigation:hidden", page.evaluate("document.getElementById('scene-nav-overlay').classList.contains('is-hidden')"))
    check("tutorial:visible", page.evaluate("!document.getElementById('scene-tutorial').hidden && document.querySelectorAll('.tutorial-target').length===1"))
    story_height = page.evaluate("Math.round(document.querySelector('.story-panel').getBoundingClientRect().height)")
    check("narrative:preserved", story_height >= 185, str(story_height))

    no_flicker = page.evaluate("""async () => {
      const shell=document.querySelector('.scene-shell');
      sceneRenderToken++;
      pendingSceneKey='';
      renderedSceneKey='image:assets/scenes/square-v1724.webp|center';
      sceneArtEl.innerHTML='<img class="scene-image" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==" alt="QA scene">';
      shell.classList.remove('is-loading');
      const before=document.querySelector('#scene-art img.scene-image');
      addLog('Information-only QA result.','system');
      renderAll();
      await new Promise(resolve=>setTimeout(resolve,120));
      const after=document.querySelector('#scene-art img.scene-image');
      return {same:before===after,loading:shell.classList.contains('is-loading')};
    }""")
    check("scene:no-flicker-info-action", no_flicker["same"] and not no_flicker["loading"], str(no_flicker))

    page.evaluate("document.getElementById('nav-toggle-btn').click()")
    check("navigation:toggle-opens", page.evaluate("!document.getElementById('scene-nav-overlay').classList.contains('is-hidden')"))
    page.evaluate("revealSceneHotspots(5000)")
    check("look:reveals-hotspots", page.evaluate("document.querySelectorAll('.hotspot.look-reveal').length>0"))

    page.evaluate("selectNearbyHotspot(currentHotspots().find(h=>h.label==='Well'))")
    selected_text = page.evaluate("document.getElementById('quick-actions').innerText.toLowerCase()")
    check("object:context-only", "look at well" in selected_text and "go north" not in selected_text and "go east" not in selected_text, selected_text)
    page.evaluate("selectedHotspotContext=null;actionsPanelExpanded=true;renderQuickActions()")
    nearby_text = page.evaluate("document.getElementById('quick-actions').innerText")
    check("nearby:fallback", "Nearby objects and characters" in nearby_text and "Well" in nearby_text, nearby_text)

    page.evaluate("startCombat('restlessSkeleton')")
    check("encounter:intro", page.evaluate("document.getElementById('encounter-dialog').open && state.pendingEncounter==='restlessSkeleton'"))
    intro_text = page.evaluate("document.getElementById('encounter-dialog').innerText")
    check("encounter:attributes", all(text in intro_text for text in ["Undead", "Threat: Low", "Resistant to Fear", "Heavy strikes"]))
    page.evaluate("beginCombatFromEncounter()")
    rect = page.evaluate("""() => {
      const r=document.querySelector('.combat-panel').getBoundingClientRect();
      return {cx:r.left+r.width/2,cy:r.top+r.height/2,vx:innerWidth/2,vy:innerHeight/2};
    }""")
    check("combat:centered", abs(rect["cx"]-rect["vx"]) < 3 and abs(rect["cy"]-rect["vy"]) < 3, str(rect))
    crop = page.evaluate("""() => {
      const img=document.getElementById('combat-enemy-art');
      const style=getComputedStyle(img);
      return {position:style.objectPosition,width:Math.round(img.getBoundingClientRect().width),height:Math.round(img.getBoundingClientRect().height)};
    }""")
    check("combat:portrait-fitted", crop["position"] != "50% 50%" and crop["width"] >= 60 and crop["height"] >= 60, str(crop))
    page.evaluate("emergencyRetreatFromCombat('QA')")

    page.evaluate("state.health=10;addItem('minor healing tonic');startCombat('thornHound');beginCombatFromEncounter();combatAction('item')")
    healing = page.evaluate("({health:state.health,qty:itemQty('minor healing tonic'),phase:state.combat.phase})")
    check("healing:works", healing["health"] == 16 and healing["qty"] == 0 and healing["phase"] == "enemy-ready", str(healing))
    page.evaluate("emergencyRetreatFromCombat('QA')")

    page.evaluate("startCombat('restlessSkeleton');beginCombatFromEncounter();combatVictory('restlessSkeleton')")
    loot_text = page.evaluate("document.getElementById('loot-dialog').innerText")
    check("rewards:gold-and-healing", "8 gold" in loot_text and "Minor Healing Tonic" in loot_text and "Restores 6 HP" in loot_text, loot_text)
    browser.close()

print(f"RESULT {sum(results)}/{len(results)}")
raise SystemExit(0 if all(results) else 1)
