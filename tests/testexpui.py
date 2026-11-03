# Experimental features stay out of sight in Settings until asked for (or until one is already on), and the
# page shows them all once the switch is on. All names and messages are made up.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
URL="http://127.0.0.1:18171/#/settings"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            pg=await (await b.new_context(viewport={"width":1000,"height":900},color_scheme=scheme)).new_page()
            errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
            await pg.goto(URL); await pg.wait_for_timeout(2000); await pg.evaluate("openSettings('')"); await pg.wait_for_timeout(800)
            await pg.click("#settings details[data-g='Experimental'] summary"); await pg.wait_for_timeout(300)
            txt=await pg.inner_text("#settings details[data-g='Experimental']")
            check("Show experimental features" in txt, f"{scheme}: the switch is there")
            check("Keep bots off the Public channel" not in txt and "Spot reworded spam" not in txt, f"{scheme}: the features are hidden while it is off")
            await pg.screenshot(path=".out_exp_off_%s.png"%scheme)
            check(not errs, f"{scheme}: no page errors "+str(errs[:1]))
        g.apply_settings({"show_experimental": True})
        pg=await (await b.new_context(viewport={"width":1000,"height":900})).new_page()
        await pg.goto(URL); await pg.wait_for_timeout(2000); await pg.evaluate("openSettings('')"); await pg.wait_for_timeout(800)
        await pg.click("#settings details[data-g='Experimental'] summary"); await pg.wait_for_timeout(300)
        txt=await pg.inner_text("#settings details[data-g='Experimental']")
        check("Keep bots off the Public channel" in txt and "Spot reworded spam" in txt and "Stop repeat sends" in txt, "switched on: all three are listed")
        g.apply_settings({"show_experimental": False, "public_bots": True})
        pg=await (await b.new_context(viewport={"width":1000,"height":900})).new_page()
        await pg.goto(URL); await pg.wait_for_timeout(2000); await pg.evaluate("openSettings('')"); await pg.wait_for_timeout(800)
        await pg.click("#settings details[data-g='Experimental'] summary"); await pg.wait_for_timeout(300)
        check("Keep bots off the Public channel" in await pg.inner_text("#settings details[data-g='Experimental']"), "a feature already on is never hidden")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
