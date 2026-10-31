# The FloodGuard page's "What FloodGuard stopped" chart in a browser: one legend entry and one table column per kind
# that has something in the last 24 hours, in light and dark, on a desktop and a phone. Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
th=int(time.time()//3600*3600)
for i in range(0,10):
    h=g.hist.setdefault(str(th-i*3600),{"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{}})
    h.update({"fc":40+i,"fcl":20+i,"fcu":10,"fca":5,"ds":6+i,"fx":0})
g.hist.setdefault(str(th-15*3600),{"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{}}).update({"fc":30,"fx":4})   # an older hour: total only
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            for vp in ({"width":1280,"height":900},{"width":375,"height":800}):
                pg=await (await b.new_context(viewport=vp,color_scheme=scheme)).new_page()
                e=[]; pg.on("pageerror",lambda x:e.append(str(x)))
                await pg.goto("http://127.0.0.1:18171/#/floodguard"); await pg.wait_for_timeout(1800)
                leg=await pg.eval_on_selector_all("#floodLegend span","s=>s.map(x=>x.textContent)")
                check(any("too far while busy" in x for x in leg) and any("Unscoped" in x for x in leg) and any("Adverts" in x for x in leg),f"{scheme} {vp['width']}: legend has the limits: {leg}")
                check(any("Damaged copies not passed on" in x for x in leg) and any("not broken down" in x for x in leg) and any("let through" in x for x in leg),f"legend has damaged, older and let-through: {leg}")
                check(not any("Wardriving" in x for x in leg),"a kind with nothing in 24 hours is left out")
                heads=await pg.eval_on_selector_all("#chartFlood + details th","s=>s.map(x=>x.textContent)")
                check(heads[0]=="Hour" and len(heads)==1+len(leg),f"one table column per legend entry: {heads}")
                segs=await pg.eval_on_selector_all("#chartFlood path","s=>[...new Set(s.map(x=>x.getAttribute('class')))].sort()")
                check({"fl","fu","fa","fd"}<=set(segs),f"the bars have a segment per kind: {segs}")
                lab=await pg.get_attribute("#chartFlood","aria-label")
                check("packets in total" in lab,"chart label: "+lab[:80])
                check(await pg.evaluate("document.documentElement.scrollWidth<=innerWidth"),f"no sideways scroll at {vp['width']}px")
                check(not e,"no page errors "+str(e))
                if scheme=="light" and vp["width"]==1280:
                    await pg.locator("#chartFlood").scroll_into_view_if_needed()
                    await pg.screenshot(path=os.environ.get("SHOT","/tmp/_fgbreak.png"))
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
