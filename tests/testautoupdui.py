# The Overview's offer of automatic updates: says why, moves to Settings once answered, can be put off, and the
# Updates page says how often GitHub was contacted. Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18194"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
sg.IN_PLUGIN=True   # an install that can update itself
g.apply_settings({"set_forget_prompt":False})   # the fuller offer (testsetforgetui.py) comes first; this is the one after it
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18194/#/"); await pg.wait_for_timeout(2000)
        sec=pg.locator("#autoUpdSec")
        check(await sec.is_visible(),"the offer is on the Overview")
        note=await pg.locator("#autoUpdNote").inner_text()
        check("Recommended" in note and "fix" in note and "Settings" in note,"says why, and where to change it later: "+note)
        await pg.locator("#autoUpd").check(); await pg.wait_for_timeout(1500)
        check(g.cfg.get("auto_update") is True,"turning it on saves the setting")
        check(not await sec.is_visible(),"once on, it leaves the Overview")
        await pg.goto("http://127.0.0.1:18194/#/updates"); await pg.wait_for_timeout(1200)
        line=await pg.locator("#uLine").inner_text()
        check("Automatic updates are on" in line,"the Updates page says it's on: "+line)
        gh=await pg.locator("#uGithub").inner_text()
        check("how many repeaters run it" in gh and "Nothing about your repeater is sent" in gh and "turn this off" in gh,"says plainly that it is counted, and how to stop: "+gh)
        g.apply_settings({"count_install":False}); await pg.reload(); await pg.wait_for_timeout(2000)
        check((await pg.locator("#uGithub").inner_text()).strip()=="","turned off: the line goes")
        g.apply_settings({"auto_update":False})
        await pg.goto("http://127.0.0.1:18194/#/"); await pg.reload(); await pg.wait_for_timeout(2000)
        check(await sec.is_visible(),"off again: offered again")
        await pg.locator("#autoUpdNo").click(); await pg.wait_for_timeout(1500)
        check(g.cfg.get("auto_update_prompt") is False and g.cfg.get("auto_update") is False,"Not now: offer put away, nothing turned on")
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(not await sec.is_visible(),"and it stays away")
        g.apply_settings({"auto_update_prompt":True,"update_check":"off"})
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(not await sec.is_visible(),"not offered while looking for versions is turned off")
        g.apply_settings({"update_check":"daily"})
        await pg.set_viewport_size({"width":375,"height":800}); await pg.reload(); await pg.wait_for_timeout(2000)
        box=await sec.bounding_box()
        check(box and box["width"]<=375,"fits a phone screen")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
