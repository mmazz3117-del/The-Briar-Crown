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

check("version:1770", 'const BUILD_VERSION = "1.7.7.0"' in index and "build=1770" in index)
check("button:explicit-type", 'id="send-btn" type="button"' in index)
check("handler:shared-robust-clear", all(token in index for token in ["clearCommandInput", "event.preventDefault()", "inputEl.blur()", "finally{clearCommandInput();}"]))

with sync_playwright() as pw:
    launch_args = {"headless": True, "args": ["--no-sandbox", "--allow-file-access-from-files"]}
    executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if executable:
        launch_args["executable_path"] = executable
    browser = pw.chromium.launch(**launch_args)
    page = browser.new_page(viewport={"width": 430, "height": 932}, is_mobile=True, has_touch=True)
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

    reset()
    page.fill("#command-input", "look")
    page.click("#send-btn")
    page.wait_for_timeout(250)
    result = page.evaluate("({value:commandInput=document.getElementById('command-input').value,last:state.lastCommand,count:state.commandHistory.filter(x=>x==='look').length})")
    check("button:clears-and-runs-once", result["value"] == "" and result["last"] == "look" and result["count"] == 1, str(result))

    # Emulate a late mobile input commit during blur. The deferred/final clear must win.
    reset()
    page.evaluate("""() => {
      const input=document.getElementById('command-input');
      input.addEventListener('blur',()=>setTimeout(()=>{input.value='look';},0),{once:true});
    }""")
    page.fill("#command-input", "look")
    page.click("#send-btn")
    page.wait_for_timeout(250)
    late = page.evaluate("({value:document.getElementById('command-input').value,last:state.lastCommand,count:state.commandHistory.filter(x=>x==='look').length})")
    check("button:late-mobile-commit-stays-cleared", late["value"] == "" and late["last"] == "look" and late["count"] == 1, str(late))

    reset()
    page.fill("#command-input", "inventory")
    page.press("#command-input", "Enter")
    page.wait_for_timeout(150)
    enter = page.evaluate("({value:document.getElementById('command-input').value,last:state.lastCommand,count:state.commandHistory.filter(x=>x==='inventory').length})")
    check("enter:clears-and-runs-once", enter["value"] == "" and enter["last"] == "inventory" and enter["count"] == 1, str(enter))

    browser.close()

print(f"RESULT {sum(results)}/{len(results)}")
raise SystemExit(0 if all(results) else 1)
