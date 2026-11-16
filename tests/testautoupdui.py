# The Overview's automatic updates switch: shows the reason to turn it on, saves the choice and says when it's on.
# Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18194"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18194/#/"); await pg.wait_for_timeout(2000)
        sw=pg.locator("#autoUpd")
        check(await sw.count()==1 and await sw.is_visible(),"the switch is on the Overview")
        check(not await sw.is_checked(),"off to begin with")
        note=await pg.locator("#autoUpdNote").inner_text()
        check("Recommended" in note and "fix" in note,"says why it's worth turning on: "+note)
        await sw.check(); await pg.wait_for_timeout(1500)
        check(g.cfg.get("auto_update") is True,"turning it on saves the setting")
        note=await pg.locator("#autoUpdNote").inner_text()
        check(note.startswith("On.") and "couple of hours" in note,"and the note says what happens now: "+note)
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(await pg.locator("#autoUpd").is_checked(),"still on after a reload")
        await pg.locator("#autoUpd").uncheck(); await pg.wait_for_timeout(1500)
        check(g.cfg.get("auto_update") is False,"and off again")
        await pg.set_viewport_size({"width":375,"height":800}); await pg.wait_for_timeout(500)
        box=await pg.locator("#autoUpdSec").bounding_box()
        check(box and box["width"]<=375,"fits a phone screen")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
