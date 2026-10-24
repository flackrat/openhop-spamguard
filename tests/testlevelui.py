# The protection level slider on the page: it shows the level's name and colour as it moves, says what the
# level does in plain words, only saves when you let go, and asks before replacing values you set yourself.
# Made-up data only.
import sys, asyncio, time
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:18171/"); await pg.wait_for_timeout(1200)
        check(await pg.text_content("#lvlName")=="Balanced" and await pg.input_value("#lvl")=="50", "starts at Balanced, 50")
        c1=await pg.evaluate("getComputedStyle(document.querySelector('#lvlSec')).getPropertyValue('--lvl')")
        await pg.evaluate("const e=document.querySelector('#lvl'); e.value=85; e.dispatchEvent(new Event('input'))")
        await pg.wait_for_timeout(200)
        c2=await pg.evaluate("getComputedStyle(document.querySelector('#lvlSec')).getPropertyValue('--lvl')")
        check(await pg.text_content("#lvlName")=="Tough" and c1!=c2, f"the name and colour follow the slider: {c1} {c2}")
        check(g.cfg["level"]==50, "nothing is saved while it is still moving")
        await pg.evaluate("document.querySelector('#lvlMore').open=true")
        txt=await pg.text_content("#lvlDetail")
        check("Held after 2 copies" in txt and "What this level does" in txt, "it says what the level does in plain words")
        check("evidence log" in txt, "and how to see what it would have held")
        bt=[x for x in await pg.query_selector_all("#lvlDetail button") if "Turn on the evidence log" in (await x.text_content())]
        check(bool(bt), "with a button right there to turn the evidence log on")
        await pg.evaluate("document.querySelector('#lvl').dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(1500)
        check(g.cfg["level"]==85, f"letting go saves it: {g.cfg['level']}")
        # a value you set yourself: asked first, and Cancel keeps it
        g.apply_settings({"slow_repeat_max":5}); await pg.wait_for_timeout(100)
        await pg.evaluate("load(true)"); await pg.wait_for_timeout(500)
        check("your own setting" in (await pg.text_content("#lvlOwn")), "values you set yourself are pointed out")
        asked=[]
        async def dlg(d): asked.append(d.message); await d.dismiss()
        pg.on("dialog",lambda d: asyncio.ensure_future(dlg(d)))
        await pg.evaluate("const e=document.querySelector('#lvl'); e.value=60; e.dispatchEvent(new Event('input')); e.dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(1800)
        check(asked and "yourself" in asked[0], "it asks before replacing them")
        check(g.cfg["level"]==60 and g.cfg["slow_repeat_max"]==5, "Cancel keeps your own value and still moves the level")
        # an exact number on the Settings page, for those who want one
        await pg.evaluate("openSettings('')"); await pg.wait_for_timeout(600)
        check(await pg.is_visible("#lvlExact"), "the Settings page has the level as a number, reached from the Overview")
        await pg.fill("#lvlExact","37"); await pg.click("#lvlExactSet"); await pg.wait_for_timeout(1800)
        check(g.cfg["level"]==37, f"typing an exact level sets it: {g.cfg['level']}")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
