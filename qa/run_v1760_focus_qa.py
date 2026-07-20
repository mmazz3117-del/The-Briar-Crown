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
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(html, wait_until="load")

    def reset(room="square", class_key="ranger"):
        page.evaluate("""args => {
          state=initialState();
          state.player={name:'QA',classKey:args.classKey,className:titleCase(args.classKey),stats:heroClasses[args.classKey].stats};
          state.room=args.room; state.visited=[args.room]; state.log=[];
          document.getElementById('start-overlay').hidden=true;
          restoreDynamicExits(); renderAll();
        }""", {"room": room, "classKey": class_key})

    check("browser:no-errors", not errors, ";".join(errors))
    check("version:1760", 'const BUILD_VERSION = "1.7.6.0"' in index and "build=1760" in index)
    check("parser:present", all(token in index for token in ["handleFlexibleCommand", "solveFlexibleToolPuzzle", "nextFlexibleHint"]))

    reset("square")
    page.evaluate("state.flags.tutorialSceneTapComplete=true;state.flags.tutorialFirstActionComplete=true;state.flags.tutorialCommandIntroShown=true;renderAll()")
    check("tutorial:command-card-visible", page.evaluate("!document.getElementById('command-tutorial').hidden"))
    tutorial_text = page.locator("#command-tutorial").inner_text()
    check("tutorial:explains-hybrid-play", "Tap objects" in tutorial_text and "type naturally" in tutorial_text and "lift the rock with a stick" in tutorial_text, tutorial_text)
    page.fill("#command-input", "look")
    page.click("#send-btn")
    page.wait_for_timeout(80)
    check("tutorial:typed-command-completes", page.evaluate("state.flags.tutorialCommandComplete && document.getElementById('command-tutorial').hidden"))

    reset("tavernCellar")
    page.evaluate("addItem('hunting knife')")
    page.evaluate("processCommand('lift the flagstone with the hunting knife')")
    result = page.evaluate("({looted:state.flags.cellarFlagstoneLooted,gold:state.gold,last:state.log.at(-1).text})")
    check("commands:reversed-tool-phrase-solves", result["looted"] and result["gold"] == 23 and "lever" in result["last"].lower(), str(result))

    reset("tavernCellar")
    page.evaluate("processCommand('lift rock with stick')")
    hint = page.evaluate("state.log.at(-1).text")
    check("commands:missing-tool-guidance", "leverage" in hint.lower() and "sturdy branch" in hint.lower() and "metal tool" in hint.lower(), hint)

    reset("tavernCellar")
    page.evaluate("processCommand('levitate the flagstone')")
    first_hint = page.evaluate("state.log.at(-1).text")
    page.evaluate("processCommand('levitate the flagstone')")
    second_hint = page.evaluate("state.log.at(-1).text")
    check("commands:graduated-hints", first_hint != second_hint and ("specific" in first_hint.lower() or "examin" in first_hint.lower()), f"{first_hint} / {second_hint}")

    reset("forgeLane")
    page.evaluate("processCommand('take dropped coins')")
    standard = page.evaluate("({taken:state.flags.forgeCoinsTaken,gold:state.gold,last:state.log.at(-1).text})")
    check("commands:standard-actions-preserved", standard["taken"] and standard["gold"] == 23, str(standard))

    reset("moonwell")
    page.evaluate("addItem('iron hook')")
    page.evaluate("processCommand('pull the shard with the iron hook')")
    direct = page.evaluate("({taken:state.flags.shardTaken,has:has('crown shard'),last:state.log.at(-1).text})")
    check("commands:creative-existing-solution", direct["taken"] and direct["has"], str(direct))

    reset("square")
    no_flicker = page.evaluate("""async () => {
      const shell=document.querySelector('.scene-shell');
      sceneRenderToken++; pendingSceneKey=''; renderedSceneKey='image:assets/scenes/square-v1724.webp|center';
      sceneArtEl.innerHTML='<img class="scene-image" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==" alt="QA scene">';
      shell.classList.remove('is-loading');
      const before=document.querySelector('#scene-art img.scene-image');
      await processCommand('look at well');
      await new Promise(resolve=>setTimeout(resolve,100));
      const after=document.querySelector('#scene-art img.scene-image');
      return {same:before===after,loading:shell.classList.contains('is-loading')};
    }""")
    check("combined:no-flicker-preserved", no_flicker["same"] and not no_flicker["loading"], str(no_flicker))

    reset("crypt")
    page.evaluate("state.flags.cryptCoffinOpened=true;startCombat('restlessSkeleton');beginCombatFromEncounter()")
    crop = page.evaluate("getComputedStyle(document.getElementById('combat-enemy-art')).objectPosition")
    check("combined:portrait-fit-preserved", crop != "50% 50%", crop)

    browser.close()

print(f"RESULT {sum(results)}/{len(results)}")
raise SystemExit(0 if all(results) else 1)
