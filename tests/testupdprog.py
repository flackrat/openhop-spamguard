# The Update box while an update installs: a percentage bar and the last two lines of the installer's
# output. Checks what the page shows, that installer text can't inject anything into the page, that a
# finished or failed update shows no bar, and that axe finds no WCAG 2.1 AA problems in light and dark.
# All text is made up. Needs Playwright with Chromium and the axe-core npm package.
import json, asyncio, os
from playwright.async_api import async_playwright
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = open(os.path.join(REPO, 'ui.html')).read()
AXE = open(os.environ.get("AXE_JS", os.path.join(REPO, "tests", ".axe", "node_modules", "axe-core", "axe.min.js"))).read()

def upd(st, **kw):
    u = {"current": "6.5.0", "latest": "6.5.1", "available": True, "installer_ready": True, "docker": False,
         "plugin": True, "managed_update": None, "checked": 0, "notes": "", "status": st}
    u.update(kw); return {"update": u}

RUNNING = {"state": "running", "message": "openHop is installing the new version (this can take a minute)...",
           "pct": 47, "lines": ["Installing collected packages: pycryptodome", "<img src=x onerror=window.__xss=1> Successfully built"]}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 420, "height": 900})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        async def h(route):
            u = route.request.url
            if u.startswith("http://sg.test/"): return await route.fulfill(body=UI, content_type="text/html")
            await route.fulfill(json={})
        await pg.route("**/*", h)
        await pg.goto("http://sg.test/#/overview"); await pg.wait_for_timeout(1500)
        await pg.add_script_tag(content=AXE)
        res = []
        async def show(data):
            await pg.evaluate("d=>renderUpdate(d)", data); await pg.wait_for_timeout(200)
        async def info():
            return await pg.evaluate("""()=>({
              callbar:[...document.querySelectorAll('#updCallout [role=progressbar]')].map(e=>e.getAttribute('aria-valuenow')),
              boxbar:[...document.querySelectorAll('#uProg [role=progressbar]')].map(e=>e.getAttribute('aria-valuenow')),
              pct:[...document.querySelectorAll('.uppct')].map(e=>e.textContent),
              lines:[...document.querySelectorAll('.uplines')].map(e=>e.textContent),
              imgs:document.querySelectorAll('.uplines img, #updCallout img').length,
              xss:window.__xss||null, call:document.querySelector('#updCallout').innerText,
              fill:[...document.querySelectorAll('.upbar i')].map(e=>e.style.width)})""")
        await show(upd(RUNNING)); a = await info()
        res += [(a["callbar"] == ["47"] and a["boxbar"] == ["47"], "the bar shows 47 in the banner and in the Updates box: " + str(a["callbar"]) + str(a["boxbar"])),
                (a["pct"] == ["47%", "47%"] and a["fill"] == ["47%", "47%"], "the percentage is written as well as drawn: " + str(a["pct"])),
                ("Installing collected packages: pycryptodome" in a["lines"][0], "the installer's last lines are shown"),
                ("<img" in a["lines"][0] and a["imgs"] == 0 and a["xss"] is None, "installer text is shown as text, never as markup"),
                ("installing the new version" in a["call"], "the banner says what it is doing")]
        for scheme in ("light", "dark"):
            await pg.evaluate(f"document.documentElement.dataset.theme='{scheme}'"); await pg.wait_for_timeout(150)
            v = await pg.evaluate("""async()=>(await axe.run({exclude:['.chart']},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
            res.append((not v, f"axe finds no WCAG 2.1 AA problems with the bar and lines ({scheme}): {v[:4]}"))
        await show(upd({"state": "running", "message": "Getting version 6.5.1...", "pct": 250, "lines": []})); a = await info()
        res.append((a["callbar"] == ["100"], "a percentage over 100 is held at 100: " + str(a["callbar"])))
        await show(upd({"requested": True})); a = await info()
        res.append((a["callbar"] == [] and a["lines"] == [] and "Updating SpamGuard" in a["call"], "a request not yet picked up shows no bar and no lines"))
        await show(upd({"state": "failed", "message": "Update failed: boom", "pct": 55, "lines": ["ERROR: no matching distribution"], "ts": 4e9}, available=False)); a = await info()
        res.append((a["callbar"] == [] and a["boxbar"] == [], "a failed update shows no progress bar"))
        await show(upd({"state": "failed", "message": "Update stopped before anything was changed. Test.", "pct": 34, "lines": [], "ts": 4e9, "can_force": True})); a = await info()
        btn = await pg.evaluate("[...document.querySelectorAll('#uBtns button')].map(b=>b.textContent+'|'+(b.getAttribute('onclick')||'')+'|'+(b.dataset.confirm||''))")
        res.append((any(x.startswith("Update anyway|") and "force:true" in x and "version:'6.5.1'" in x and "uninstalled" in x for x in btn), "a stopped update offers Update anyway, with a warning: " + str([x[:40] for x in btn])))
        await show(upd({"state": "failed", "message": "Update failed: boom", "pct": 55, "lines": [], "ts": 4e9})); btn = await pg.evaluate("[...document.querySelectorAll('#uBtns button')].map(b=>b.textContent)")
        res.append(("Update anyway" not in btn, "an ordinary failure doesn't offer it: " + str(btn)))
        res.append((not errs, "no page errors: " + str(errs)))
        bad = [m for c, m in res if not c]
        for m in bad: print("FAIL", m)
        print(f"{len(res)-len(bad)} passed, {len(bad)} failed")
        await b.close()
        raise SystemExit(1 if bad else 0)
asyncio.run(main())
