#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys, shutil
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
VERSION = "1.7.2.9"
ART_VERSION = "1.7.2.9"
CONTRACT = json.loads((Path(__file__).parent / "contracts.json").read_text())
results = []

def check(name, ok, detail=""):
    ok = bool(ok)
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), name, detail)

index = (ROOT / "index.html").read_text()
manifest = json.loads((ROOT / "manifest.json").read_text())
sw = (ROOT / "service-worker.js").read_text()

check("version:index", VERSION in index)
check("version:manifest", manifest.get("version") == VERSION, str(manifest.get("version")))
check("version:cache", f"briar-crown-v{VERSION}" in sw)
check("qa:portable-root", "Path(__file__).resolve().parents[1]" in (ROOT / "qa/run_qa.py").read_text())
check("menu:scene-test-button", 'id="scene-tour-btn"' in index)
check("map:illustrated-asset", (ROOT / "assets/ui/world-map-v1726.png").exists())
check("map:illustrated-renderer", "Illustrated Discovered Map" in index and "world-map-v1726.png" in index)

# Every local asset referenced by the app exists.
refs = sorted(set(re.findall(r"assets/(?:scenes|ui)/[A-Za-z0-9._-]+", index)))
missing = [r for r in refs if not (ROOT / r).exists()]
check("assets:all-app-references-exist", not missing, ", ".join(missing))

# Every pre-cached service worker file exists.
sw_refs = re.findall(r'"(\./[^\"]+)"', sw.split("self.addEventListener", 1)[0])
sw_missing = [r for r in sw_refs if r != "./" and not (ROOT / r[2:]).exists()]
check("service-worker:all-precache-files-exist", not sw_missing, ", ".join(sw_missing))

# Production scene manifest protects the replacement art from fallback/thumbnail regressions.
prod_path = ROOT / "assets/scenes/production-manifest-v1729.json"
prod = json.loads(prod_path.read_text()) if prod_path.exists() else {"assets": {}}
check("assets:production-manifest", prod.get("version") == ART_VERSION, str(prod.get("version")))
for name, meta in prod.get("assets", {}).items():
    p = ROOT / "assets/scenes" / name
    exists = p.exists()
    check(f"asset:{name}:exists", exists)
    if not exists:
        continue
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    check(f"asset:{name}:checksum", digest == meta.get("sha256"))
    im = Image.open(p).convert("RGB")
    check(f"asset:{name}:dimensions", im.width >= 1200 and im.height >= 900, str(im.size))
    top = im.crop((0, 0, im.width, max(10, im.height // 12)))
    bottom = im.crop((0, im.height - max(10, im.height // 12), im.width, im.height))
    edge_var = (sum(ImageStat.Stat(top).var) / 3, sum(ImageStat.Stat(bottom).var) / 3)
    check(f"asset:{name}:no-flat-letterbox", edge_var[0] > 8 and edge_var[1] > 8, f"{edge_var[0]:.1f}/{edge_var[1]:.1f}")
    check(f"asset:{name}:mobile-size", p.stat().st_size <= 750000, str(p.stat().st_size))
    try:
        Image.open(p).verify(); decodes=True
    except Exception as exc:
        decodes=False
    check(f"asset:{name}:decodes", decodes)

priority_active = {
    "square": "square-v1724.webp",
    "forgeLane": "forge-lane-v1724.webp",
    "chapelRoad": "chapel-road-v1724.webp",
    "willowTrail": "willow-trail-v1724.webp",
    "flowerClearing": "flower-clearing-v1724.webp",
    "fallenLog": "fallen-log-v1724.webp",
    "cottage": "witch-cottage-interior-v1724.webp",
    "moonwell": "moonwell-v1724.webp",
    "secretTunnel": "hidden-passage-v1724.webp",
    "secretAlcove": "collapsed-alcove-v1724.webp",
    "thornHedgePass": "thorn-hedge-pass-v1729.webp",
    "brokenWatchCrossing": "broken-watch-crossing-v1729.webp",
    "outerGateApproach": "outer-gate-approach-v1729.webp",
}
for room_id, filename in priority_active.items():
    check(f"asset-map:{room_id}", f'{room_id}: "assets/scenes/{filename}"' in index)

# Browser-level contracts.
html = index.replace("<head>", f'<head><base href="file://{ROOT}/">', 1)
with sync_playwright() as pw:
    launch_args = {"headless": True, "args": ["--no-sandbox", "--allow-file-access-from-files"]}
    system_chromium = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if system_chromium:
        launch_args["executable_path"] = system_chromium
    browser = pw.chromium.launch(**launch_args)
    page = browser.new_page(viewport={"width": 430, "height": 932})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content(html, wait_until="load")
    check("browser:no-page-errors", not errors, "; ".join(errors))
    check("ui:map-top-button", page.locator("#map-btn .label").inner_text().strip() == "Map")
    check("ui:satchel-label", page.locator("#backpack-btn small").inner_text().strip() == "Satchel")
    viewport_meta = page.locator('meta[name="viewport"]').get_attribute("content") or ""
    check("zoom:page-pinch-disabled", "user-scalable=no" in viewport_meta and "maximum-scale=1" in viewport_meta, viewport_meta)
    check("ui:no-visible-scene-marker-badges", "sceneMarkersEl.appendChild" not in index and ".scene-markers { display:none" in index)
    apoth_actions = page.evaluate("rooms.apothecaryDoor.actions")
    forge_actions = page.evaluate("rooms.forgeDoor.actions")
    check("doors:apothecary-art-state", "enter apothecary" in apoth_actions and "open door" not in apoth_actions, str(apoth_actions))
    check("doors:forge-art-state", "enter forge" in forge_actions and "open door" not in forge_actions, str(forge_actions))
    chapel_spot = page.evaluate("rooms.chapelYard.hotspots.find(h=>h.label==='Chapel')")
    check("hotspots:chapel-aligned", bool(chapel_spot) and chapel_spot["x"] >= 62 and chapel_spot["w"] >= 38, str(chapel_spot))
    alcove_actions = page.evaluate("() => { state=initialState(); state.room='secretAlcove'; return currentActions().map(normalize); }")
    check("actions:alcove-rubble-visible", "try to move rubble" in alcove_actions, str(alcove_actions))
    check("map:zoom-controls", 'data-map-zoom="in"' in index and 'data-map-zoom="out"' in index and 'data-map-reset' in index)
    check("map:current-location-marker", "YOU ARE HERE" in index and "wm-you-dot" in index)
    check("map:full-screen-viewer", "height:100dvh!important" in index and "world-map-v1726.png" in index)
    check("map:no-crossing-overlay-lines", ".wm-route { display:none!important; }" in index and 'const edgesSvg = "";' in index)
    check("opening:art-present", (ROOT / "assets/ui/opening-v1726.webp").exists() and "opening-v1726.webp" in index)
    check("opening:version-visible", "Version 1.7.2.9" in index and 'id="opening-enter-btn"' in index)
    hub = page.evaluate("rooms.square.exits")
    check("navigation:four-way-hub", hub == {"north":"tavernApproach","east":"forgeLane","south":"castleRoad","west":"chapelRoad"}, str(hub))
    check("navigation:named-action-labels", "navigationDestinationNames" in index and "Go ${titleCase(compass[1])}" in index)
    check("tavern:hatch-dynamic-label", 'selectedHotspotContext.hotspot.label="Cellar Hatch"' in index)
    check("tavern:hatch-progress-repair", "const cellarRouteProgress" in index and "cellarHatchIsDiscovered" in index)
    check("map:close-safe-area", "padding-top:env(safe-area-inset-top)" in index and "data-map-close" in index)
    check("ui:command-dock-uses-visual-viewport", "visibleViewportMetrics" in index and "window.visualViewport" in index and "display:grid!important" in index)
    check("ui:viewport-height-clamped", "Math.min(...heightCandidates)" in index and "--app-width" in index)
    check("ui:orientation-multipass-settle", "settleViewportAfterOrientation" in index and "[0, 80, 180, 360, 700]" in index)
    check("ui:orientation-forced-reflow", "forceViewportLayoutReflow" in index and 'style.setProperty("display", "none", "important")' in index)
    check("keyboard:visual-viewport-dock", "keyboard-open" in index and "Math.round(vv.height)" in index and "--viewport-top" in index)
    check("d20:animated-check-dialog", 'id="dice-dialog"' in index and "animatedCheck" in index and "@keyframes d20-roll" in index)
    check("combat:prototype-present", 'id="combat-dialog"' in index and "enemyCatalog" in index and "combatAction" in index)
    check("combat:required-actions", all(f'data-combat-action="{a}"' in index for a in ["attack","defend","item","flee"]))
    check("ui:redundant-action-helpers-removed", "Available actions" not in index and "Tap an action below" not in index)
    check("performance:navigation-not-network-blocked", "if (destinationPath) await preloadScene(destinationPath)" not in index)
    check("performance:scene-test-lazy", 'loading="lazy" decoding="async"' in index)
    check("performance:scene-cache-first", "const isScene" in sw and "cached || (await refresh)" in sw)
    check("ui:bounded-mobile-story-panel", "grid-template-rows: auto auto minmax(0, 1fr) auto" in index and "overflow: hidden !important" in index)
    check("ui:larger-mobile-status", "font-size: 12px !important" in index and "min-width: 68px !important" in index and "min-width: 58px !important" in index)
    apoth_approach = page.evaluate("rooms.apothecaryApproach.hotspots.find(h=>h.label==='Apothecary Door')")
    check("hotspots:apothecary-approach-door-aligned", bool(apoth_approach) and 58 <= apoth_approach["x"] <= 72 and apoth_approach["w"] >= 32, str(apoth_approach))
    check("ui:hotspot-selection-scrolls-actions", 'controls.scrollIntoView({ behavior: "smooth", block: "nearest" })' in index)

    # Existing saves that reached the cellar/tunnel must never regress to a Scuffed Floor label.
    page.evaluate("""() => {
      state=initialState(); state.schemaVersion=1723; state.room='tavern';
      state.visited=['square','tavern','tavernCellar','secretTunnel','secretAlcove'];
      state.flags.tunnelCoinsTaken=true; state.flags.hatchDiscoveryConfirmed=false;
      migrateState(); renderAll();
    }""")
    check("tavern:legacy-progress-repairs-hatch", page.evaluate("state.flags.hatchDiscoveryConfirmed") is True)
    check("tavern:legacy-progress-label-is-cellar-hatch", page.locator("#hotspots .hotspot").filter(has_text="Cellar Hatch").count() >= 1)

    def reset(room="square"):
        page.evaluate("""room => {
          state=initialState();
          state.player={name:'QA Hero',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};
          state.room=room; state.visited=[room]; state.log=[]; restoreDynamicExits();
          document.getElementById('start-overlay').hidden=true; renderAll();
        }""", room)

    # Route graph is a real scene-by-scene chain and does not skip back to Forest Edge.
    required_edges = CONTRACT["route_rebuild"]["required_edges"]
    edges = page.evaluate("worldMapEdges")
    undirected = {tuple(sorted(x)) for x in edges}
    for a, b in required_edges:
        check(f"route:map-edge:{a}-{b}", tuple(sorted((a, b))) in undirected)
    check("route:east-road-to-forest", page.evaluate("rooms.eastRoad.exits.east") == "forestEdge")
    check("route:deep-forest-return", page.evaluate("rooms.whisperingForest.exits.west") == "fallenLog")
    check("route:cottage-is-deep", page.evaluate("rooms.whisperingForest.exits.north") == "cottageApproach")
    check("route:cottage-return", page.evaluate("rooms.cottageApproach.exits.south") == "whisperingForest")
    check("route:castle-road-to-thorn-pass", page.evaluate("rooms.castleRoad.exits.south") == "thornHedgePass")
    check("route:thorn-pass-to-watch", page.evaluate("rooms.thornHedgePass.exits.south") == "brokenWatchCrossing")
    check("route:watch-to-outer-approach", page.evaluate("rooms.brokenWatchCrossing.exits.south") == "outerGateApproach")
    check("route:outer-approach-to-gate", page.evaluate("rooms.outerGateApproach.exits.south") == "castleGate")
    check("route:gate-return-to-approach", page.evaluate("rooms.castleGate.exits.north") == "outerGateApproach")

    # Discoverables appear before collection and disappear after collection.
    discoverables = CONTRACT["route_rebuild"]["discoverables"]
    for room_id, action in discoverables.items():
        reset(room_id)
        acts = page.evaluate("currentActions().map(normalize)")
        check(f"discoverable:{room_id}:available", action in acts, str(acts))
        page.evaluate("action => processCommand(action)", action)
        after = page.evaluate("currentActions().map(normalize)")
        check(f"discoverable:{room_id}:consumed", action not in after, str(after))

    reset("forgeLane")
    before_gold = page.evaluate("state.gold")
    page.evaluate("processCommand('take dropped coins')")
    check("discoverable:forge-coins-value", page.evaluate("state.gold") == before_gold + 3)

    # Tavern hatch/action gating.
    reset("tavern")
    acts = page.evaluate("currentActions().map(normalize)")
    for forbidden in CONTRACT["scenes"]["tavern"]["fresh_forbidden"]:
        check(f"contract:tavern:fresh-forbids:{forbidden}", forbidden not in acts, str(acts))
    innkeeper = page.evaluate("currentHotspots().find(x=>x.label==='Innkeeper')")
    page.evaluate("h=>{selectedHotspotContext={hotspot:h,room:state.room,view:currentView()};renderQuickActions();}", innkeeper)
    innkeeper_text = " ".join(page.locator("#quick-actions button").all_inner_texts()).lower()
    check("contract:tavern:no-ask-before-discovery-context", "ask about cellar" not in innkeeper_text, innkeeper_text)
    page.evaluate("processCommand('look at cellar door')")
    check("contract:tavern:hatch-discovered", page.evaluate("state.flags.hatchDiscoveryConfirmed") is True)
    acts = page.evaluate("currentActions().map(normalize)")
    check("contract:tavern:ask-after-discovery", "ask innkeeper about cellar" in acts, str(acts))
    check("contract:tavern:no-go-down-before-open", "go down" not in acts, str(acts))
    page.evaluate("state.flags.cellarUnlocked=true; processCommand('open cellar hatch')")
    check("contract:tavern:go-down-after-open", "go down" in page.evaluate("currentActions().map(normalize)"))

    # Cottage action gating.
    reset("cottage")
    check("contract:cottage:no-go-down-fresh", "go down" not in page.evaluate("currentActions().map(normalize)"))
    page.evaluate("processCommand('move rug')")
    check("contract:cottage:no-go-down-after-rug-only", "go down" not in page.evaluate("currentActions().map(normalize)"))
    page.evaluate("state.flags.trapdoorUnlocked=true; processCommand('open trapdoor')")
    check("contract:cottage:go-down-after-open", "go down" in page.evaluate("currentActions().map(normalize)"))

    # Map and Scene Test remain directly available.
    reset("square")
    page.locator("#map-btn").click()
    check("navigation:map-opens", page.locator("#map-dialog").evaluate("d=>d.open"))
    check("navigation:map-background-present", page.locator(".world-map-bg").count() == 1)
    page.locator("#map-dialog [data-close]").click()
    page.locator("#menu-btn").click()
    check("navigation:scene-test-listed", "Scene Test" in page.locator("#menu-dialog").inner_text())
    page.locator("#scene-tour-btn").click()
    check("navigation:scene-test-opens", page.locator("#scene-dialog").evaluate("d=>d.open"))
    page.locator("#scene-dialog [data-close]").click()

    reset("apothecary")
    elowen = page.evaluate("currentHotspots().find(h=>h.label==='Elowen')")
    cabinets = page.evaluate("currentHotspots().find(h=>h.label==='Cabinets')")
    check("hotspots:elowen-visible-position", bool(elowen) and elowen["x"] < 40, str(elowen))
    check("hotspots:elowen-not-covered", bool(elowen) and bool(cabinets) and elowen["x"] > cabinets["x"] + cabinets["w"]/2, f"{elowen}/{cabinets}")
    reset("blacksmith")
    check("npc:merrin-art-v1724", "forge-interior-v1724.webp" in page.evaluate("sceneImageMap.blacksmith"))
    reset("chapel")
    check("chapel:explore-action", "explore chapel" in page.evaluate("defaultSceneActions().map(normalize)"))
    reset("oldCemeteryPath")
    cemetery_exits=page.evaluate("rooms.oldCemeteryPath.exits")
    check("cemetery:east-and-south-exits", cemetery_exits.get("east") == "chapelYard" and cemetery_exits.get("south") == "chapelRoad", str(cemetery_exits))

    # v1.7.2.9 treasure, crypt and combat prototype.
    reset("tavernCellar")
    cellar_actions=page.evaluate("currentActions().map(normalize)")
    check("treasure:cellar-barrel-action", "search old barrel" in cellar_actions, str(cellar_actions))
    check("treasure:cellar-flagstone-action", "pry up loose flagstone" in cellar_actions, str(cellar_actions))
    reset("secretTunnel")
    tunnel_actions=page.evaluate("currentActions().map(normalize)")
    check("treasure:tunnel-loose-stone", "search loose stone" in tunnel_actions, str(tunnel_actions))
    check("treasure:tunnel-wall-niche", "search wall niche" in tunnel_actions, str(tunnel_actions))
    check("treasure:tunnel-bones", "inspect old bones" in tunnel_actions, str(tunnel_actions))
    reset("crypt")
    crypt_actions=page.evaluate("currentActions().map(normalize)")
    check("crypt:coffin-action", "open stone coffin" in crypt_actions, str(crypt_actions))
    check("crypt:burial-shelf-action", "search burial shelf" in crypt_actions, str(crypt_actions))
    check("crypt:quick-actions-show-coffin", "open stone coffin" in page.evaluate("defaultSceneActions().map(normalize)"))
    reset("thornHedgePass")
    road_actions=page.evaluate("currentActions().map(normalize)")
    check("encounter:thorn-hound-action", "investigate growl" in road_actions, str(road_actions))
    page.evaluate("startCombat('thornHound')")
    check("combat:dialog-opens", page.locator("#combat-dialog").evaluate("d=>d.open"))
    check("combat:enemy-is-thorn-hound", page.locator("#combat-enemy-name").inner_text().strip() == "Thorn Hound")
    page.evaluate("combatVictory('thornHound')")
    check("combat:victory-flag", page.evaluate("state.flags.thornHoundDefeated") is True)
    check("combat:victory-item", page.evaluate("has('briar fang')") is True)
    reset("crypt")
    page.evaluate("startCombat('restlessSkeleton')")
    check("combat:skeleton-dialog", page.locator("#combat-enemy-name").inner_text().strip() == "Restless Skeleton")
    page.evaluate("combatVictory('restlessSkeleton')")
    check("combat:skeleton-reward", page.evaluate("has('ancient chapel charm')") is True)
    stats=page.evaluate("adventureStats()")
    check("d20:derived-stats", all(k in stats for k in ["might","wits","resolve","luck","defense"]), str(stats))
    page.locator("#command-input").focus()
    page.wait_for_timeout(120)
    check("keyboard:focus-class", page.evaluate("document.body.classList.contains('keyboard-open')") is True)
    page.locator("#command-input").evaluate("el=>el.blur()")
    page.wait_for_timeout(120)

    # Structural checks across all rooms.
    bad_exits = page.evaluate("""() => Object.entries(rooms).flatMap(([id,r]) => Object.entries(r.exits||{}).filter(([d,to])=>!rooms[to]).map(([d,to])=>id+':'+d+'->'+to))""")
    check("graph:all-exits-target-real-rooms", not bad_exits, str(bad_exits))
    no_exit = page.evaluate("Object.entries(rooms).filter(([id,r])=>!Object.keys(r.exits||{}).length).map(([id])=>id)")
    check("graph:all-rooms-have-exit", not no_exit, str(no_exit))
    bad_spots = page.evaluate("""() => {
      const bad=[];
      for (const [id,r] of Object.entries(rooms)) for (const h of (r.hotspots||[])) {
        if (!h.command || h.x<0 || h.y<0 || h.x>100 || h.y>100 || (h.w||0)<=0 || (h.h||0)<=0 || h.x+(h.w||0)>115 || h.y+(h.h||0)>115) bad.push(id+':'+h.label);
      }
      return bad;
    }""")
    check("hotspots:valid-bounds-and-actions", not bad_spots, str(bad_spots))
    duplicates = page.evaluate("""() => {
      const original=state, bad=[];
      for (const id of Object.keys(rooms)) {
        state=initialState(); state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats}; state.room=id; restoreDynamicExits();
        const keys=currentActions().map(canonicalActionKey); if (new Set(keys).size!==keys.length) bad.push(id);
      }
      state=original; restoreDynamicExits(); renderAll(); return bad;
    }""")
    check("actions:no-duplicates", not duplicates, str(duplicates))

    # Rotate landscape and back to portrait. The flexible story row must recover
    # without leaving a large black gap and controls must remain inside the viewport.
    page.evaluate("document.getElementById('start-overlay').hidden=true")
    page.set_viewport_size({"width": 852, "height": 393})
    page.evaluate("window.dispatchEvent(new Event('orientationchange'))")
    page.wait_for_timeout(250)
    page.set_viewport_size({"width": 430, "height": 932})
    page.evaluate("window.dispatchEvent(new Event('orientationchange'))")
    page.wait_for_timeout(850)
    rotation_geometry = page.evaluate("""() => {
      const app=document.querySelector('.app').getBoundingClientRect();
      const scene=document.querySelector('.scene-shell').getBoundingClientRect();
      const story=document.querySelector('.story-panel').getBoundingClientRect();
      const controls=document.querySelector('.controls').getBoundingClientRect();
      return {app,scene,story,controls,innerHeight:window.innerHeight,cssHeight:getComputedStyle(document.documentElement).getPropertyValue('--app-height')};
    }""")
    check("ui:orientation-app-height-recovers", abs(rotation_geometry["app"]["height"] - rotation_geometry["innerHeight"]) <= 3, str(rotation_geometry))
    gap = rotation_geometry["story"]["top"] - rotation_geometry["scene"]["bottom"]
    check("ui:orientation-no-black-middle-gap", gap <= 20 and rotation_geometry["story"]["height"] > 60, str(rotation_geometry))
    check("ui:orientation-controls-in-viewport", rotation_geometry["controls"]["bottom"] <= rotation_geometry["innerHeight"] + 3, str(rotation_geometry))
    check("ui:orientation-no-horizontal-overflow", rotation_geometry["story"]["right"] <= rotation_geometry["app"]["right"] + 1 and rotation_geometry["controls"]["right"] <= rotation_geometry["app"]["right"] + 1, str(rotation_geometry))

    browser.close()

passed = sum(ok for _, ok, _ in results)
total = len(results)
report = [f"The Briar Crown v{VERSION} QA Report", f"Passed: {passed}/{total}", ""]
for name, ok, detail in results:
    report.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
(ROOT / f"QA_REPORT_v{VERSION}.txt").write_text("\n".join(report) + "\n")
print(f"\nRESULT {passed}/{total}")
if passed != total:
    sys.exit(1)
