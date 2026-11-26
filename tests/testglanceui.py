# The Overview's "Protection right now" panel, Health's freshness list and the Health page's settings change history,
# in the browser, with made-up data. Symbols as well as colour, so it reads without colour.
import sys, os, asyncio
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g.loop_beat=time.time(); g.apply_settings({"mode":"protect"}); g.poll_once(); g.loop_beat=time.time()
def beat():
    while True:
        g.loop_beat=time.time(); time.sleep(2)
threading.Thread(target=beat,daemon=True).start()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1100,"height":1000})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(2500)
        check(await pg.is_visible("#protSec"),"the panel is on the Overview")
        check("Protected" in await pg.text_content("#protPill"),"it says Protected: %s"%await pg.text_content("#protPill"))
        parts=await pg.eval_on_selector_all("#protParts dt","els=>els.map(e=>e.textContent)")
        check({"Mode","openHop","Checking","Rules in openHop","FloodGuard"}<=set(parts),"each part is shown: %s"%parts)
        check(await pg.is_hidden("#ohModeNote"),"no openHop mode note while it repeats")
        g.oh_mode="no_tx"; await pg.wait_for_timeout(9000)
        t=await pg.text_content("#ohModeNote"); check(await pg.is_visible("#ohModeNote") and "No TX" in t and "nothing to stop" in t,"openHop on No TX is pointed out by the mode: %s"%t)
        check("Not repeating" in await pg.text_content("#protPill"),"and the panel says not repeating")
        g.oh_mode="forward"
        g.apply_settings({"paused":True}); await pg.wait_for_timeout(9000)
        t=await pg.text_content("#protPill"); check("✕" in t and "Not protected" in t,"paused shows not protected, with a symbol: %s"%t)
        check(await pg.is_visible("#protWhy"),"and a line saying why")
        g.apply_settings({"paused":False})
        await pg.goto("http://127.0.0.1:18171/#/health"); await pg.wait_for_timeout(2000)
        rows=await pg.eval_on_selector_all("#hFresh li","els=>els.map(e=>e.textContent)")
        check(len(rows)==7 and any("Rules confirmed" in r for r in rows),"Health lists when each part last worked: %s"%rows[:3])
        h=await pg.eval_on_selector_all("#histList li","els=>els.map(e=>e.textContent)")
        check(any("Pause" in x for x in h) and any("You, on the page" in x for x in h),"the change history shows what changed and who: %s"%h[:2])
        for i in range(14): g.apply_settings({"level":40+i})
        await pg.wait_for_timeout(9000)
        n=await pg.locator("#histList li").count(); check(n==10 and await pg.is_visible("#histMore"),"ten at first, with Show all: %s %s"%(n,len(g.settings_history)))
        await pg.click("#histMore"); await pg.wait_for_timeout(300)
        check(await pg.locator("#histList li").count()>10,"Show all shows the rest")
        check(not errs,f"no page errors {errs}")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); os._exit(1 if fail else 0)
