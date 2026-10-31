# The hint about the experimental learning setting: shown once on the Overview, gone for good when dismissed
# or opened, and not shown at all when the setting is already on. All names and messages are made up.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
URL="http://127.0.0.1:18171/#/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            pg=await (await b.new_context(viewport={"width":1000,"height":900},color_scheme=scheme)).new_page()
            errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
            await pg.goto(URL); await pg.wait_for_timeout(2000)
            txt=await pg.inner_text("#banners")
            check("learn from your spam marks" in txt and "xperimental" in txt, f"{scheme}: hint shown while the setting is off")
            check("record-only" in txt and "leaves this device" in txt, f"{scheme}: says briefly what it does")
            check(len(txt)<260, f"{scheme}: short ({len(txt)} characters)")
            await pg.screenshot(path=os.path.join(".out_sense_hint_%s.png"%scheme))
            await pg.click("#senseHint button")
            check(await pg.locator("#senseHint").count()==0, f"{scheme}: Dismiss removes it")
            await pg.reload(); await pg.wait_for_timeout(2000)
            check(await pg.locator("#senseHint").count()==0, f"{scheme}: and it stays gone after a reload")
            await pg.evaluate("localStorage.clear()"); await pg.reload(); await pg.wait_for_timeout(2000)
            check(await pg.locator("#senseHint").count()==1, f"{scheme}: back after clearing browser data")
            await pg.click("#senseHint a"); await pg.wait_for_timeout(600)
            check(await pg.evaluate("localStorage.getItem('sgDismissSense')")=="1", f"{scheme}: Take a look counts as seen")
            check("xperimental" in await pg.inner_text("#settings"), f"{scheme}: Take a look lands on the setting")
            check(not errs, f"{scheme}: no page errors "+str(errs[:1]))
        # already switched on: never shown
        g.apply_settings({"text_sense": True})
        pg=await (await b.new_context(viewport={"width":1000,"height":900})).new_page()
        await pg.goto(URL); await pg.wait_for_timeout(2000)
        check(await pg.locator("#senseHint").count()==0, "not shown when it is already switched on")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
