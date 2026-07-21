#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys, shutil
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
VERSION = "1.7.7.0"
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
    check("map:current-location-marker", "HERE" in index and "wm-you-dot" in index)
    check("map:full-screen-viewer", "height:100dvh!important" in index and "world-map-v1726.png" in index)
    check("map:no-crossing-overlay-lines", ".wm-route { display:none!important; }" in index and 'const edgesSvg = "";' in index)
    check("opening:art-present", (ROOT / "assets/ui/opening-v1730.webp").exists() and "opening-v1730.webp" in index)
    check("opening:version-visible", 'const BUILD_VERSION = "1.7.7.0"' in index and 'id="opening-enter-btn"' in index)
    check("opening:animated-scroll-structure", all(token in index for token in ["ancient-scroll","scroll-roll-top","scroll-roll-bottom","parchment-unfurl","showLoreScreen"]))
    check("opening:hidden-step-isolation-css", '.lore-step[hidden], .class-step[hidden], .opening-title-step[hidden]' in index)
    page.evaluate("showTitleScreen()")
    page.click("#opening-enter-btn")
    page.click("#new-adventure-btn")
    check("opening:lore-only-visible", page.locator("#lore-step").is_visible() and not page.locator("#class-step").is_visible())
    check("opening:scroll-rolls-visible", page.locator(".scroll-roll-top").is_visible() and page.locator(".scroll-roll-bottom").is_visible())
    page.click("#lore-continue-btn")
    check("opening:hero-only-visible", page.locator("#class-step").is_visible() and not page.locator("#lore-step").is_visible())
    hero_geom=page.locator("#class-step").evaluate("e=>({top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom,h:e.clientHeight,scroll:e.scrollHeight,inner:window.innerHeight})")
    check("opening:hero-screen-fills-mobile", hero_geom["top"] <= 1 and hero_geom["bottom"] <= hero_geom["inner"]+1 and hero_geom["h"] > 500, str(hero_geom))
    check("opening:hero-cards-interactive", page.locator("#class-grid .class-card").count() >= 4)
    hub = page.evaluate("rooms.square.exits")
    check("navigation:four-way-hub", hub == {"north":"tavernApproach","east":"forgeLane","south":"castleRoad","west":"chapelRoad"}, str(hub))
    check("navigation:named-action-labels", "navigationDestinationNames" in index and "Go ${titleCase(compass[1])}" in index)
    check("tavern:hatch-dynamic-label", 'selectedHotspotContext.hotspot.label="Cellar Hatch"' in index)
    check("tavern:hatch-progress-repair", "const cellarRouteProgress" in index and "cellarHatchIsDiscovered" in index)
    check("map:close-safe-area", "padding-top:env(safe-area-inset-top)" in index and "data-map-close" in index)
    check("ui:command-dock-uses-visual-viewport", "visibleViewportMetrics" in index and "window.visualViewport" in index and "display:grid!important" in index)
    check("ui:viewport-height-fills-standalone", "Math.max(...heightCandidates)" in index and "window.screen.height" in index and "--app-width" in index)
    check("ui:orientation-multipass-settle", "settleViewportAfterOrientation" in index and "[0, 80, 180, 360, 700]" in index)
    check("ui:orientation-forced-reflow", "forceViewportLayoutReflow" in index and 'style.setProperty("display", "none", "important")' in index)
    check("keyboard:visual-viewport-dock", "keyboard-open" in index and "Math.round(vv.height)" in index and "--viewport-top" in index)
    check("d20:animated-check-dialog", 'id="dice-dialog"' in index and "animatedCheck" in index and "@keyframes d20-roll" in index)
    check("combat:prototype-present", 'id="combat-dialog"' in index and "enemyCatalog" in index and "combatAction" in index)
    check("v1750:actions-collapsed-default", 'let actionsPanelExpanded = storageGet(ACTION_PANEL_PREF_KEY) === "true"' in index)
    check("v1750:navigation-hidden-default", 'let sceneNavigationVisible = storageGet(NAV_VISIBLE_PREF_KEY) === "true"' in index)
    check("v1750:navigation-toggle", 'id="nav-toggle-btn"' in index and "updateNavigationToggle" in index)
    check("v1750:nearby-fallback", "Nearby objects and characters" in index and "selectNearbyHotspot" in index)
    check("v1750:look-reveal", "revealSceneHotspots" in index and "look-reveal" in index)
    check("v1750:first-time-tutorial", 'id="scene-tutorial"' in index and "tutorialSceneTapComplete" in index)
    check("v1750:encounter-card", 'id="encounter-dialog"' in index and "beginCombatFromEncounter" in index)
    check("v1750:creature-art-assets", all((ROOT/p).exists() for p in ["assets/ui/thorn-hound-v1750.webp","assets/ui/restless-skeleton-v1750.webp"]))
    check("v1750:healing-rewards", "field bandage" in index and "minor healing tonic" in index and "healingItemCatalog" in index)
    check("v1750:gold-reward-visual", "loot-gold-icon" in index)
    check("v1751:no-flicker-scene-key", "renderedSceneKey" in index and "pendingSceneKey" in index and "sceneKey === renderedSceneKey" in index)
    check("v1751:combat-portrait-crop", "combatPosition" in index and "--combat-art-position" in index)
    check("v1760:contextual-command-parser", "handleFlexibleCommand" in index and "solveFlexibleToolPuzzle" in index and "nextFlexibleHint" in index)
    check("v1760:command-tutorial", 'id="command-tutorial"' in index and "tutorialCommandComplete" in index and "submitTypedCommand" in index)
    check("v1760:combined-hotfix-preserved", "sceneKey === renderedSceneKey" in index and "combatPosition" in index)
    check("v1761:typed-command-clears-input", 'inputEl.value="";' in index and "submitTypedCommand" in index)
    check("v1770:send-button-mobile-clear", 'id="send-btn" type="button"' in index and "clearCommandInput" in index and "event.preventDefault()" in index and "finally{clearCommandInput();}" in index)
    check("combat:required-actions", all(f'data-combat-action="{a}"' in index for a in ["attack","defend","item","flee","continue"]))
    check("combat:emergency-retreat-control", 'id="combat-close-btn"' in index and "emergencyRetreatFromCombat" in index)
    check("combat:finally-cleanup", "finally {" in index and "combatUiBusy=false" in index and "resetCombatPresentation" in index)
    check("combat:resume-pending-state", "resumePendingInteractionState" in index and "state.pendingLoot=state.pendingLoot" in index)
    check("skills:unique-combat-practice", "grantSkillPractice" in index and "victory-restlessSkeleton" in index and "victory-thornHound" in index)
    check("combat:player-acknowledged-phases", "enemy-ready" in index and "Continue — Enemy Turn" in index and "combat-history" in index)
    check("equipment:dialog-present", 'id="equipment-dialog"' in index and "Equipment &amp; Loadout" in index)
    check("ui:safe-area-dialog-css", all(token in index for token in ["--panel-safe-top:env(safe-area-inset-top,0px)","dialog.safe-area-dialog[open]","inset-block-start:calc(var(--panel-safe-top)","overscroll-behavior:contain"]))
    check("ui:tall-panels-use-safe-area", all(f'id="{panel}" class="safe-area-dialog"' in index or (panel=="equipment-dialog" and 'id="equipment-dialog" class="equipment-dialog safe-area-dialog"' in index) for panel in ["inventory-dialog","equipment-dialog","skills-dialog","shop-dialog","menu-dialog","scene-dialog"]))
    check("equipment:hero-art-present", (ROOT / "assets/ui/rowan-equipment-v1742.webp").exists() and "rowan-equipment-v1742.webp" in index)
    check("equipment:slots-present", all(f'{slot}:{{label:' in index for slot in ["weapon","offhand","armor","boots","charm","ring","belt"]))
    check("equipment:combat-formulas-present", "stats.attack" in index and "stats.defense" in index and "equipmentTotals" in index and "Damage:" in index)
    check("audio:central-recovery-controller", all(token in index for token in ["ensureMusicPlaying","recoverMusicAfterInterruption","visibilitychange","pageshow","musicWatchdog","Tap to Resume"]))
    check("audio:timer-clears-before-reschedule", "function clearMusicTimer" in index and "musicTimer=null;scheduleHarpPhrase()" in index)
    check("searches:one-attempt-helper", "runOneAttemptCheck" in index and "You may try again" not in index)
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
    # Chapter One combat lifecycle: a completed battle must never lock the next encounter.
    reset("thornHedgePass")
    road_actions=page.evaluate("currentActions().map(normalize)")
    check("encounter:thorn-hound-action", "investigate growl" in road_actions, str(road_actions))
    page.evaluate("startCombat('thornHound')")
    check("combat:encounter-intro-opens", page.locator("#encounter-dialog").evaluate("d=>d.open"))
    check("combat:encounter-intro-enemy", page.locator("#encounter-name").inner_text().strip() == "Thorn Hound")
    check("combat:encounter-intro-art", "thorn-hound-v1750.webp" in (page.locator("#encounter-art").get_attribute("src") or ""))
    check("combat:encounter-attributes", all(x in page.locator("#encounter-dialog").inner_text() for x in ["Briar Beast","Threat: Moderate","Thorn Hide","Fire and clean blades"]))
    page.evaluate("beginCombatFromEncounter()")
    check("combat:dialog-opens", page.locator("#combat-dialog").evaluate("d=>d.open"))
    check("combat:enemy-is-thorn-hound", page.locator("#combat-enemy-name").inner_text().strip() == "Thorn Hound")
    first_buttons=page.evaluate("combatButtonsState()")
    check("combat:first-encounter-actions-enabled", not first_buttons["attack"] and not first_buttons["defend"] and not first_buttons["flee"], str(first_buttons))
    check("combat:first-die-reset", page.locator("#combat-die").inner_text().strip() == "?")
    page.evaluate("combatVictory('thornHound')")
    check("combat:victory-flag", page.evaluate("state.flags.thornHoundDefeated") is True)
    check("combat:loot-dialog", page.locator("#loot-dialog").evaluate("d=>d.open"))
    page.evaluate("collectPendingLoot()")
    check("combat:victory-item", page.evaluate("has('briar fang')") is True)
    check("combat:thorn-healing-reward", page.evaluate("has('field bandage')") is True)
    check("combat:thorn-practice-awarded", page.evaluate("state.skillUses.Combat") == 1, str(page.evaluate("state.skillUses")))

    # The exact user-reported sequence: Skeleton victory, then Thorn Hound encounter.
    reset("crypt")
    page.evaluate("startCombat('restlessSkeleton');beginCombatFromEncounter()")
    check("combat:skeleton-dialog", page.locator("#combat-enemy-name").inner_text().strip() == "Restless Skeleton")
    page.evaluate("combatVictory('restlessSkeleton')")
    page.evaluate("collectPendingLoot()")
    check("combat:skeleton-reward", page.evaluate("has('ancient chapel charm')") is True)
    check("combat:skeleton-healing-reward", page.evaluate("has('minor healing tonic')") is True)
    check("combat:skeleton-practice-awarded", page.evaluate("state.skillUses.Combat") == 1, str(page.evaluate("state.skillUses")))
    page.evaluate("state.room='thornHedgePass';startCombat('thornHound');beginCombatFromEncounter()")
    second_buttons=page.evaluate("combatButtonsState()")
    check("combat:second-encounter-actions-enabled", not second_buttons["attack"] and not second_buttons["defend"] and not second_buttons["flee"], str(second_buttons))
    check("combat:second-encounter-die-reset", page.locator("#combat-die").inner_text().strip() == "?")
    check("combat:second-encounter-message-reset", "emerges" in page.locator("#combat-message").inner_text().lower())
    page.evaluate("emergencyRetreatFromCombat('QA retreat')")
    check("combat:emergency-retreat-closes", not page.locator("#combat-dialog").evaluate("d=>d.open") and page.evaluate("state.combat") is None)

    # A real attack action must always return controls to an enabled state.
    reset("thornHedgePass")
    page.evaluate("startCombat('thornHound');beginCombatFromEncounter();state.combat.enemyHp=1;Math.random=()=>0.99")
    page.evaluate("combatAction('attack')")
    check("combat:attack-opens-reward", page.locator("#loot-dialog").evaluate("d=>d.open"))
    page.evaluate("collectPendingLoot()")
    page.evaluate("startCombat('restlessSkeleton');beginCombatFromEncounter()")
    after_action_buttons=page.evaluate("combatButtonsState()")
    check("combat:post-animation-next-actions-enabled", not after_action_buttons["attack"] and not after_action_buttons["defend"] and not after_action_buttons["flee"], str(after_action_buttons))
    page.evaluate("emergencyRetreatFromCombat('QA retreat')")

    # Encounter introductions, pending rewards and active battles recover correctly after a simulated reload.
    reset("thornHedgePass")
    page.evaluate("startCombat('thornHound');const saved=JSON.stringify(state);state=JSON.parse(saved);migrateState();renderAll();resumePendingInteractionState()")
    check("combat:pending-intro-survives-reload", page.locator("#encounter-dialog").evaluate("d=>d.open") and page.evaluate("state.pendingEncounter") == "thornHound")
    page.evaluate("retreatBeforeCombat()")
    reset("crypt")
    page.evaluate("startCombat('restlessSkeleton');beginCombatFromEncounter();combatVictory('restlessSkeleton');const saved=JSON.stringify(state);state=JSON.parse(saved);migrateState();renderAll();resumePendingInteractionState()")
    check("combat:pending-loot-survives-reload", page.locator("#loot-dialog").evaluate("d=>d.open") and page.evaluate("state.pendingLoot.enemyId") == "restlessSkeleton")
    page.evaluate("collectPendingLoot()")
    reset("thornHedgePass")
    page.evaluate("startCombat('thornHound');beginCombatFromEncounter();state.combat.enemyHp=4;const saved=JSON.stringify(state);state=JSON.parse(saved);migrateState();renderAll();resumePendingInteractionState()")
    resumed_buttons=page.evaluate("combatButtonsState()")
    check("combat:active-battle-resumes", page.locator("#combat-dialog").evaluate("d=>d.open") and page.evaluate("state.combat.enemyHp") == 4)
    check("combat:resumed-actions-enabled", not resumed_buttons["attack"] and not resumed_buttons["defend"] and not resumed_buttons["flee"], str(resumed_buttons))
    page.evaluate("emergencyRetreatFromCombat('QA retreat')")

    # Prior saves receive missing practice exactly once.
    page.evaluate("""() => {state=initialState();state.player={name:'QA',classKey:'druid',className:'Druid',stats:heroClasses.druid.stats};state.flags.cryptSkeletonDefeated=true;state.schemaVersion=1731;state.skillPracticeFlags={};migrateState();} """)
    check("skills:retroactive-skeleton-practice", page.evaluate("state.skillUses.Combat") == 1, str(page.evaluate("state.skillUses")))
    page.evaluate("migrateState()")
    check("skills:retroactive-practice-idempotent", page.evaluate("state.skillUses.Combat") == 1, str(page.evaluate("state.skillUses")))

    # Crypt objects align with the visible artwork and progress to completed states.
    reset("crypt")
    coffin=page.evaluate("currentHotspots().find(h=>h.label==='Stone Coffin')")
    reliquary=page.evaluate("currentHotspots().find(h=>h.label==='Reliquary')")
    check("crypt:coffin-hotspot-visible-object", coffin["x"] >= 70 and coffin["y"] >= 50, str(coffin))
    check("crypt:coffin-reliquary-do-not-overlap", coffin["x"] >= reliquary["x"]+reliquary["w"]-2, f"{coffin}/{reliquary}")
    page.evaluate("state.flags.cryptBurialShelfAttempted=true;state.flags.cryptBurialShelfLooted=true;state.flags.cryptSkeletonDefeated=true;state.flags.cryptCoffinLooted=true;state.flags.reliquaryOpen=true;state.flags.sigilTaken=true;renderAll()")
    done_actions=page.evaluate("currentActions().map(normalize)")
    done_spots=page.evaluate("currentHotspots().map(h=>({label:h.label,command:h.command}))")
    check("crypt:completed-actions-removed", all(a not in done_actions for a in ["search burial shelf","open stone coffin","search open coffin","open reliquary","use silver token on reliquary"]), str(done_actions))
    check("crypt:completed-hotspot-labels", any(h["label"]=="Empty Coffin" for h in done_spots) and any(h["label"]=="Empty Burial Shelf" for h in done_spots) and any(h["label"]=="Open Reliquary" for h in done_spots), str(done_spots))

    # Ten clean back-to-back encounter lifecycles catch stale UI flags.
    lifecycle_ok=page.evaluate("""() => {
      for(let i=0;i<10;i++){
        state=initialState();state.player={name:'QA',classKey:'druid',className:'Druid',stats:heroClasses.druid.stats};state.room='crypt';
        startCombat('restlessSkeleton');beginCombatFromEncounter();let a=combatButtonsState();if(a.attack||a.defend||a.flee||!a.continue)return false;combatVictory('restlessSkeleton');collectPendingLoot();
        state.room='thornHedgePass';startCombat('thornHound');beginCombatFromEncounter();const b=combatButtonsState();if(b.attack||b.defend||b.flee||!b.continue||document.getElementById('combat-die').textContent!=='?')return false;emergencyRetreatFromCombat('QA');
      }return true;
    }""")
    check("combat:ten-consecutive-lifecycles", lifecycle_ok)

    # Player results remain visible until Continue explicitly begins the enemy turn.
    reset("thornHedgePass")
    page.evaluate("startCombat('thornHound');beginCombatFromEncounter();Math.random=()=>0.5")
    page.evaluate("combatAction('attack')")
    phased=page.evaluate("({phase:state.combat.phase,message:state.combat.message,rollText:state.combat.rollText,buttons:combatButtonsState(),history:state.combat.history})")
    check("combat:player-result-persists", phased["phase"] == "enemy-ready" and phased["message"].startswith("You:") and phased["buttons"]["continue"] is False and phased["buttons"]["attack"] is True, str(phased))
    check("combat:player-roll-in-history", len(phased["history"]) == 1 and phased["history"][0].startswith("You:"), str(phased["history"]))
    page.evaluate("combatAction('continue')")
    enemy_phase=page.evaluate("({phase:state.combat.phase,message:state.combat.message,buttons:combatButtonsState(),history:state.combat.history})")
    check("combat:enemy-turn-requires-continue", enemy_phase["phase"] == "player" and "Thorn Hound:" in enemy_phase["message"] and enemy_phase["buttons"]["attack"] is False, str(enemy_phase))
    page.evaluate("emergencyRetreatFromCombat('QA')")

    # Prominent new scene objects are wired and persist completed states.
    reset("thornHedgePass")
    pack=page.evaluate("currentHotspots().find(h=>h.label==='Abandoned Pack')")
    check("hotspots:abandoned-pack-present", bool(pack) and pack["x"] <= 75 and pack["w"] >= 20, str(pack))
    page.evaluate("processCommand('search abandoned pack')")
    pack_after=page.evaluate("({flag:state.flags.abandonedPackSearched,actions:currentActions().map(normalize),spot:currentHotspots().find(h=>h.label==='Empty Pack')})")
    check("hotspots:abandoned-pack-completes", pack_after["flag"] is True and "search abandoned pack" not in pack_after["actions"] and bool(pack_after["spot"]), str(pack_after))

    reset("brokenWatchCrossing")
    page.evaluate("processCommand('examine ruined watch post')")
    post_after=page.evaluate("({flag:state.flags.watchPostExamined,last:state.log.at(-1)?.text||'',spot:currentHotspots().find(h=>h.label==='Searched Watch Post')})")
    check("hotspots:watch-post-meaningful", post_after["flag"] is True and "nothing unusual" not in post_after["last"].lower() and bool(post_after["spot"]), str(post_after))

    # Chance searches are one-attempt-only on failure, including after save migration.
    reset("brokenWatchCrossing")
    page.evaluate("Math.random=()=>0;processCommand('search overturned wagon')")
    wagon_once=page.evaluate("({attempted:state.flags.watchWagonAttempted,looted:state.flags.watchWagonLooted,gold:state.gold,actions:currentActions().map(normalize),spot:currentHotspots().find(h=>h.label==='Searched Wagon')})")
    page.evaluate("processCommand('search overturned wagon')")
    wagon_twice=page.evaluate("({gold:state.gold,attempted:state.flags.watchWagonAttempted,actions:currentActions().map(normalize)})")
    check("searches:wagon-one-attempt", wagon_once["attempted"] is True and wagon_once["looted"] is False and "search overturned wagon" not in wagon_once["actions"] and bool(wagon_once["spot"]) and wagon_twice["gold"] == wagon_once["gold"], f"{wagon_once}/{wagon_twice}")
    page.evaluate("const saved=JSON.stringify(state);state=JSON.parse(saved);migrateState();renderAll()")
    check("searches:wagon-attempt-persists-reload", page.evaluate("state.flags.watchWagonAttempted && !currentActions().map(normalize).includes('search overturned wagon')"))

    # Defeated encounter triggers become meaningful post-battle observations.
    reset("thornHedgePass")
    page.evaluate("state.flags.thornHoundDefeated=true;renderAll()")
    eyes=page.evaluate("currentHotspots().find(h=>h.label==='Fading Tracks')")
    page.evaluate("processCommand('look at fading tracks')")
    check("hotspots:defeated-eyes-transform", bool(eyes) and eyes["command"] == "look at fading tracks" and page.evaluate("state.combat===null"), str(eyes))

    # Full hotspot look/examine audit: no generic no-op result is allowed.
    no_op_hotspots=page.evaluate("""async () => {
      const bad=[];
      for(const [rid,r] of Object.entries(rooms)){
        for(const h of (r.hotspots||[])){
          const c=normalize(h.command);
          if(!/^(look|examine|inspect|study|listen|read|ring)/.test(c))continue;
          if(/inspect cracked wall/.test(c))continue;
          state=initialState();state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};state.room=rid;state.log=[];
          await processCommand(c);
          const text=String(state.log.at(-1)?.text||'').toLowerCase();
          if(text.includes('nothing unusual')||text.includes('could not carry out'))bad.push(`${rid}:${h.label}:${c}`);
          document.querySelectorAll('dialog[open]').forEach(d=>d.close());
        }
      }
      return bad;
    }""")
    check("hotspots:no-look-flicker-noops", not no_op_hotspots, str(no_op_hotspots))
    empty_contexts=page.evaluate("""() => {
      const bad=[];
      for(const [rid,r] of Object.entries(rooms)){
        state=initialState();state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};state.room=rid;
        for(const h of currentHotspots())if(!contextualActionsForHotspot(h).length)bad.push(`${rid}:${h.label}`);
      }
      return bad;
    }""")
    check("hotspots:all-have-context-actions", not empty_contexts, str(empty_contexts))

    # Synthetic audio context verifies interruption recovery without real speakers.
    audio_state=page.evaluate("""async () => {
      clearMusicTimer();audioContext=null;musicUnlocked=false;musicNeedsGesture=false;musicEnabled=true;
      class P{setValueAtTime(){} exponentialRampToValueAtTime(){}}
      class N{constructor(){this.frequency=new P();this.gain=new P()}connect(){return this}start(){}stop(){}}
      class C{constructor(){this.state='suspended';this.currentTime=0;this.destination={};this.l=[]}createOscillator(){return new N()}createGain(){return new N()}addEventListener(n,f){if(n==='statechange')this.l.push(f)}async resume(){this.state='running';this.l.forEach(f=>f())}async suspend(){this.state='suspended';this.l.forEach(f=>f())}}
      window.AudioContext=C;window.webkitAudioContext=C;
      const first=await ensureMusicPlaying(true);const started=!!musicTimer&&audioContext.state==='running'&&!musicNeedsGesture;
      audioContext.state='suspended';audioContext.l.forEach(f=>f());const interrupted=musicNeedsGesture&&!musicTimer;
      const resumed=await ensureMusicPlaying(true);const recovered=resumed&&!!musicTimer&&audioContext.state==='running'&&!musicNeedsGesture;
      clearMusicTimer();return {first,started,interrupted,recovered,label:document.getElementById('music-toggle-btn').textContent};
    }""")
    check("audio:interruption-recovers", all(audio_state[k] for k in ["first","started","interrupted","recovered"]), str(audio_state))

    # The shortest Chapter One scene must still fill the phone through the controls.
    reset("thornHedgePass")
    page.evaluate("state.log=[{text:'Short scene.',type:'system'}];renderAll();syncVisibleViewportHeight()")
    short_geom=page.evaluate("() => {const a=document.querySelector('.app').getBoundingClientRect(),c=document.querySelector('.controls').getBoundingClientRect();return {appBottom:a.bottom,controlsBottom:c.bottom,inner:window.innerHeight,appHeight:a.height}}")
    check("ui:short-scene-no-bottom-gap", abs(short_geom["appBottom"]-short_geom["inner"]) <= 3 and abs(short_geom["controlsBottom"]-short_geom["inner"]) <= 3, str(short_geom))

    stats=page.evaluate("adventureStats()")
    check("d20:derived-stats", all(k in stats for k in ["might","wits","resolve","luck","defense"]), str(stats))

    # Equipment & Loadout: base/current/preview stats and combat calculations.
    page.evaluate("""() => {
      document.querySelectorAll('dialog[open]').forEach(d=>d.close());
      state=initialState();
      state.player={name:'Rowan',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};
      state.skills.Combat=2;
      addItem('iron dagger');addItem('short sword');addItem('wooden shield');addItem('ancient chapel charm');
      document.getElementById('start-overlay').hidden=true;
      renderAll();showEquipment('iron dagger');
    }""")
    check("equipment:dialog-opens", page.locator("#equipment-dialog").evaluate("d=>d.open"))
    page.evaluate("""() => {document.documentElement.style.setProperty('--panel-safe-top','52px');document.documentElement.style.setProperty('--panel-safe-bottom','20px');document.documentElement.style.setProperty('--panel-edge-buffer','12px');}""")
    page.evaluate("document.getElementById('equipment-dialog').close();showEquipment('iron dagger')")
    safe_geom=page.evaluate("""() => {const d=document.getElementById('equipment-dialog'),h=d.querySelector('.modal-head'),b=d.querySelector('.modal-body'),r=d.getBoundingClientRect(),hr=h.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height,inner:window.innerHeight,headTop:hr.top,bodyClient:b.clientHeight,bodyScroll:b.scrollHeight,display:getComputedStyle(d).display};}""")
    check("equipment:safe-top-buffer", safe_geom["top"] >= 63 and safe_geom["headTop"] >= safe_geom["top"]-1, str(safe_geom))
    check("equipment:safe-bottom-and-internal-scroll", safe_geom["bottom"] <= safe_geom["inner"]-31 and safe_geom["bodyClient"] > 0 and safe_geom["bodyScroll"] >= safe_geom["bodyClient"] and safe_geom["display"] == "flex", str(safe_geom))
    check("equipment:all-seven-slots-render", page.locator("[data-loadout-slot]").count() == 7, str(page.locator("[data-loadout-slot]").count()))
    check("equipment:hero-character-rendered", page.locator(".loadout-hero-art img").count() == 1 and "rowan-equipment-v1742.webp" in (page.locator(".loadout-hero-art img").get_attribute("src") or ""))
    equip_preview=page.evaluate("({base:combatStatBundle().base,current:combatStatBundle().current,preview:combatStatBundle(projectedLoadout('iron dagger')).current})")
    check("equipment:base-current-preview", equip_preview["base"]["attack"] == 4 and equip_preview["current"]["attack"] == 4 and equip_preview["preview"]["attack"] == 6 and equip_preview["preview"]["damageMin"] == 3 and equip_preview["preview"]["damageMax"] == 6, str(equip_preview))
    page.evaluate("equipItem('iron dagger');equipItem('wooden shield');equipItem('ancient chapel charm');renderEquipment()")
    equipped_stats=page.evaluate("combatStatBundle().current")
    check("equipment:weapon-shield-charm-stats", equipped_stats["attack"] == 6 and equipped_stats["defense"] == 13 and equipped_stats["damageMin"] == 3 and equipped_stats["damageMax"] == 6, str(equipped_stats))
    check("equipment:cards-show-equipped-items", "Iron Dagger" in page.locator("#equipment-body").inner_text() and "Wooden Shield" in page.locator("#equipment-body").inner_text() and "Ancient Chapel Charm" in page.locator("#equipment-body").inner_text())
    equip_geom=page.locator("#equipment-body").evaluate("e=>({client:e.clientWidth,scroll:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight})")
    check("equipment:mobile-no-horizontal-overflow", equip_geom["scroll"] <= equip_geom["client"] + 1, str(equip_geom))
    page.locator("#equipment-dialog [data-close]").click()
    page.evaluate("""() => {document.documentElement.style.removeProperty('--panel-safe-top');document.documentElement.style.removeProperty('--panel-safe-bottom');document.documentElement.style.removeProperty('--panel-edge-buffer');}""")

    # Legacy shield slot migrates to the new Off-Hand slot and survives save/reload.
    legacy_equipment=page.evaluate("""() => {
      state=initialState();state.player={name:'Legacy',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};
      addItem('wooden shield');state.equipment={shield:'wooden shield',weapon:null};state.schemaVersion=1741;migrateState();
      const first=JSON.parse(JSON.stringify(state.equipment));const saved=JSON.stringify(state);state=JSON.parse(saved);migrateState();
      return {first,after:state.equipment,defense:adventureStats().defense};
    }""")
    check("equipment:legacy-shield-migrates", legacy_equipment["first"]["offhand"] == "wooden shield" and legacy_equipment["after"]["offhand"] == "wooden shield" and legacy_equipment["defense"] == 12, str(legacy_equipment))

    # Removing an equipped final copy safely clears its slot.
    removed=page.evaluate("""() => {state=initialState();state.player={name:'QA',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};addItem('iron dagger');equipItem('iron dagger');removeItem('iron dagger',1);return {weapon:state.equipment.weapon,has:has('iron dagger')};}""")
    check("equipment:removed-item-unequips", removed["weapon"] is None and removed["has"] is False, str(removed))

    # Equipped Attack, Defense and Damage modifiers appear in real battle rolls.
    page.evaluate("""() => {
      state=initialState();state.player={name:'QA Knight',classKey:'knight',className:'Knight',stats:heroClasses.knight.stats};state.skills.Combat=2;
      addItem('iron dagger');addItem('wooden shield');addItem('ancient chapel charm');equipItem('iron dagger');equipItem('wooden shield');equipItem('ancient chapel charm');
      state.room='thornHedgePass';startCombat('thornHound');beginCombatFromEncounter();Math.random=()=>0.5;
    }""")
    page.evaluate("combatAction('attack')")
    geared_attack=page.evaluate("({phase:state.combat.phase,message:state.combat.message,stats:adventureStats()})")
    check("combat:equipped-attack-used", geared_attack["phase"] == "enemy-ready" and "Combat 2" in geared_attack["message"] and "Iron Dagger 2" in geared_attack["message"] and "Damage: d4" in geared_attack["message"] and geared_attack["stats"]["attack"] == 6, str(geared_attack))
    page.evaluate("combatAction('continue')")
    geared_defense=page.evaluate("({message:state.combat.message,stats:adventureStats()})")
    check("combat:equipped-defense-used", "vs Defense 13" in geared_defense["message"] and "Gear 2" in geared_defense["message"] and geared_defense["stats"]["defense"] == 13, str(geared_defense))
    page.evaluate("state.combat.phase='player';combatAction('defend')")
    page.evaluate("combatAction('continue')")
    defended=page.evaluate("({message:state.combat.message,pending:state.combat.pendingDefend,phase:state.combat.phase})")
    check("combat:defend-bonus-once", "Defend 2" in defended["message"] and "vs Defense 15" in defended["message"] and defended["pending"] is False and defended["phase"] == "player", str(defended))
    page.evaluate("emergencyRetreatFromCombat('QA')")
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
