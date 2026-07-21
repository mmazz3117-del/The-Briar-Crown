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

    def reset():
        page.evaluate("""() => {
          state=initialState();
          state.player={name:'QA',classKey:'ranger',className:'Ranger',stats:heroClasses.ranger.stats};
          state.room='square'; state.visited=['square']; state.log=[];
          state.flags.tutorialSceneTapComplete=true;
          state.flags.tutorialFirstActionComplete=true;
          state.flags.tutorialCommandComplete=true;
          document.getElementById('start-overlay').hidden=true;
          restoreDynamicExits(); renderAll();
        }""")

    check("browser:no-errors", not errors, ";".join(errors))
    check("version:1761", 'const BUILD_VERSION = "1.7.6.1"' in index and "build=1761" in index)

    reset()
    page.fill("#command-input", "look")
    page.click("#send-btn")
    page.wait_for_timeout(80)
    click_result = page.evaluate("({value:document.getElementById('command-input').value,last:state.lastCommand,logged:state.commandHistory.at(-1)})")
    check("input:button-clears", click_result["value"] == "" and click_result["last"] == "look" and click_result["logged"] == "look", str(click_result))

    reset()
    page.fill("#command-input", "inventory")
    page.press("#command-input", "Enter")
    page.wait_for_timeout(80)
    enter_result = page.evaluate("({value:document.getElementById('command-input').value,last:state.lastCommand,logged:state.commandHistory.at(-1)})")
    check("input:enter-clears", enter_result["value"] == "" and enter_result["last"] == "inventory" and enter_result["logged"] == "inventory", str(enter_result))

    reset()
    page.fill("#command-input", "lift rock with stick")
    page.click("#send-btn")
    page.wait_for_timeout(80)
    contextual = page.evaluate("({value:document.getElementById('command-input').value,last:state.log.at(-1).text})")
    check("input:contextual-command-still-runs", contextual["value"] == "" and len(contextual["last"]) > 10, str(contextual))

    reset()
    page.fill("#command-input", "   ")
    page.click("#send-btn")
    blank = page.evaluate("document.getElementById('command-input').value")
    check("input:blank-not-submitted", blank == "   ", repr(blank))

    browser.close()

print(f"RESULT {sum(results)}/{len(results)}")
raise SystemExit(0 if all(results) else 1)
