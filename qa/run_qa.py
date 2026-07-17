#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys, shutil
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
VERSION = "1.7.2.2"
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
check("map:illustrated-asset", (ROOT / "assets/ui/world-map-v1722.webp").exists())
check("map:illustrated-renderer", "Illustrated Discovered Map" in index and "world-map-v1722.webp" in index)

# Every local asset referenced by the app exists.
refs = sorted(set(re.findall(r"assets/(?:scenes|ui)/[A-Za-z0-9._-]+", index)))
missing = [r for r in refs if not (ROOT / r).exists()]
check("assets:all-app-references-exist", not missing, ", ".join(missing))

# Every pre-cached service worker file exists.
sw_refs = re.findall(r'"(\./[^\"]+)"', sw.split("self.addEventListener", 1)[0])
sw_missing = [r for r in sw_refs if r != "./" and not (ROOT / r[2:]).exists()]
check("service-worker:all-precache-files-exist", not sw_missing, ", ".join(sw_missing))

# Production scene manifest protects the replacement art from fallback/thumbnail regressions.
prod_path = ROOT / "assets/scenes/production-manifest-v1722.json"
prod = json.loads(prod_path.read_text()) if prod_path.exists() else {"assets": {}}
check("assets:production-manifest", prod.get("version") == VERSION)
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

priority_active = {
    "square": "square-v1722.webp",
    "forgeLane": "forge-lane-v1722.webp",
    "chapelRoad": "chapel-road-v1722.webp",
    "willowTrail": "willow-trail-v1722.webp",
    "flowerClearing": "flower-clearing-v1722.webp",
    "fallenLog": "fallen-log-v1722.webp",
    "cottage": "witch-cottage-interior-v1722.webp",
    "moonwell": "moonwell-v1722.webp",
    "secretTunnel": "hidden-passage-v1722.webp",
    "secretAlcove": "collapsed-alcove-v1722.webp",
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
    check("zoom:browser-pinch", "user-scalable=yes" in viewport_meta and "maximum-scale=5" in viewport_meta, viewport_meta)
    check("zoom:map-pinch", "touch-action: pan-x pan-y pinch-zoom" in index)

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
    check("route:deep-forest-return", page.evaluate("rooms.whisperingForest.exits.south") == "fallenLog")
    check("route:cottage-is-deep", page.evaluate("rooms.whisperingForest.exits.west") == "cottageApproach")
    check("route:cottage-return", page.evaluate("rooms.cottageApproach.exits.east") == "whisperingForest")

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
