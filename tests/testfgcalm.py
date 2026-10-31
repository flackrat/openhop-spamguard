# FloodGuard on the Overview and its own page: amber for a flood that has just started, calm wording once it has
# been holding flood packets back for an hour or more (on a busy site that is the normal state, not an incident),
# and a pointer to the busy limit after a day. Also checks accessibility in light and dark. All values made up.
import asyncio, os, time
from playwright.async_api import async_playwright
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = open(os.path.join(REPO, 'ui.html')).read()
AXE = open(os.environ.get("AXE_JS", os.path.join(REPO, "tests", ".axe", "node_modules", "axe-core", "axe.min.js"))).read()

def fgd(age_h, **kw):
    now = time.time()
    f = {"enabled": True, "radio_known": True, "learning": False, "relearning": False, "acting": True, "limit": 8,
         "since": now - age_h * 3600, "busy": 27.0, "peak": 41.0, "level": 15, "auto": ["flood_busy_percent"],
         "learn_days": 3, "learn_start": now - 4 * 86400, "learn_until": now - 86400, "learnt": {}, "episodes": 3,
         "flood_share": 0.8, "unscoped": 32, "advert": 8, "floor": 8, "reach": None, "rules": []}
    f.update(kw)
    return {"mode": "protect", "paused": False, "settings": {}, "metrics": {"floodguard": f, "hourly": [], "d1": {}}}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 420, "height": 900})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        async def h(route):
            if route.request.url.startswith("http://sg.test/"): return await route.fulfill(body=UI, content_type="text/html")
            await route.fulfill(json={})
        await pg.route("**/*", h)
        await pg.goto("http://sg.test/#/overview"); await pg.wait_for_timeout(1500)
        await pg.add_script_tag(content=AXE)
        res = []
        async def show(d):
            await pg.evaluate("d=>{renderFloodNav(d);renderFloodPage(d)}", d); await pg.wait_for_timeout(150)
        async def info():
            return await pg.evaluate("""()=>({
              cls:(document.querySelector('#fgCallout .callout')||{}).className||'', call:document.querySelector('#fgCallout').innerText,
              tag:document.querySelector('#fgBrandTag').textContent, tcls:document.querySelector('#fgBrandTag').className,
              page:document.querySelector('#fgCard').innerText, ptag:(document.querySelector('#fgCard .health-head .tag')||{}).className||'',
              ptext:(document.querySelector('#fgCard .health-head .tag')||{}).textContent||'',
              link:[...document.querySelectorAll('#fgCard a')].map(a=>a.getAttribute('href'))})""")
        await show(fgd(0.2)); a = await info()
        res += [("info" not in a["cls"] and "containing a flood" in a["call"], "a flood that has just started is amber on the Overview: " + a["cls"]),
                (a["tag"] == "Flood" and "would" in a["tcls"], "and its brand tag says Flood in amber: " + a["tag"]),
                ("Containing a flood" in a["page"] and "would" in a["ptag"], "and so does the FloodGuard page"),
                ("a day or more" not in a["page"], "with no long-running note yet")]
        await show(fgd(5)); a = await info()
        res += [("info" in a["cls"] and "FloodGuard is active" in a["call"] and "containing a flood" not in a["call"], "after hours it is a calm notice on the Overview: " + a["cls"]),
                ("27%" in a["call"] and "15%" in a["call"], "which still says the radio is 27% busy against the 15% limit"),
                (a["tag"] == "Active" and "plain" in a["tcls"], "brand tag: " + a["tag"]),
                (a["ptext"] == "holding back floods" and "plain" in a["ptag"], "page tag: " + a["ptext"]),
                ("a day or more" not in a["page"], "no long-running note before a day")]
        await show(fgd(70)); a = await info()
        res += [("a day or more" in a["page"] and "#/settings" in a["link"], "after a day the page points at the busy limit in Settings: " + str(a["link"])),
                ("raises its own busy limit" in a["page"], "and says FloodGuard is raising its own limit while it is automatic"),
                ("FloodGuard is active" in a["call"], "the Overview stays calm")]
        await show(fgd(70, auto=[])); a = await info()
        res.append(("raises its own busy limit" not in a["page"], "a limit you set yourself isn't described as automatic"))
        await show(fgd(70, acting=False, learning=True)); a = await info()
        res.append(("only counting" in a["call"] and "info" in a["cls"], "still only counting while it learns: unchanged wording"))
        # short enough for a phone: the notices were most of the screen before
        await show(fgd(5)); a = await info()
        res.append((len(a["call"]) < 150, f"the Overview notice is short ({len(a['call'])} characters)"))
        await show(fgd(0.2)); a = await info()
        res.append((len(a["call"]) < 140, f"and so is a fresh flood's ({len(a['call'])} characters)"))
        # interference shows on the Overview, on its own or with a flood, and not when there is none
        jam = {"enabled": True, "since": time.time() - 900, "rise": 12.4, "range": 41, "current": -100, "baseline": -112}
        d = fgd(5, limit=None, since=None); d["metrics"]["interference"] = jam; await show(d); a = await info()
        res.append(("Interference on the radio" in a["call"] and "12 dB" in a["call"] and "41%" in a["call"], "interference is on the Overview: " + a["call"][:60]))
        res.append((len(a["call"]) < 150, f"in one short notice ({len(a['call'])} characters)"))
        d = fgd(0.2); d["metrics"]["interference"] = jam; await show(d); a = await info()
        res.append(("containing a flood" in a["call"] and "Interference on the radio" in a["call"], "with a flood as well, both are shown"))
        d = fgd(5, limit=None, since=None); d["metrics"]["interference"] = {"enabled": True}; await show(d); a = await info()
        res.append((a["call"].strip() == "", "no interference and no flood: nothing on the Overview"))
        # FloodGuard not yet knowing the usual route length says so rather than claiming to act
        await show(fgd(0.2, acting=False, waiting_reach=True)); a = await info()
        res.append(("until it knows your routes" in a["call"] and "info" in a["cls"], "the Overview says it is only counting until it knows the routes: " + a["call"][:70]))
        res.append(("how far packets normally come" in a["page"], "and the page says why nothing is held back"))
        await show(fgd(0.2, acting=False, waiting_reach=True, limit=None, since=None)); a = await info()
        res.append(("needs to hear about 200 flood packets" in a["page"], "also when there is no flood: " + a["page"][:60].replace("\n"," ")))
        for scheme in ("light", "dark"):
            await pg.evaluate(f"document.documentElement.dataset.theme='{scheme}'")
            for age in (0.2, 70):
                await show(fgd(age)); await pg.wait_for_timeout(100)
                v = await pg.evaluate("""async()=>(await axe.run({exclude:['.chart']},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
                res.append((not v, f"axe finds no WCAG 2.1 AA problems ({scheme}, on for {age} h): {v[:4]}"))
        res.append((not errs, "no page errors: " + str(errs)))
        bad = [m for c, m in res if not c]
        for m in bad: print("FAIL", m)
        print(f"{len(res)-len(bad)} passed, {len(bad)} failed")
        await b.close()
        raise SystemExit(1 if bad else 0)
asyncio.run(main())
