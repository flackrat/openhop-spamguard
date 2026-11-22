# The Overview's "Look after itself" offer: says what it turns on in plain words, takes one tap, then leaves the
# Overview (and the separate updates offer stays away while it is shown). Not now changes nothing else. Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18198"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
sg.IN_PLUGIN=True   # an install that can update itself
KEYS=("auto_protect","level_auto","level_auto_early","evidence_log","route_auto","auto_update")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18198/#/"); await pg.wait_for_timeout(2000)
        sec=pg.locator("#sfSec")
        check(await sec.is_visible(),"offered on the Overview")
        check(not await pg.locator("#autoUpdSec").is_visible(),"one offer at a time: the updates offer waits")
        note=await pg.locator("#sfNote").inner_text()
        for w in ("install by themselves","protection level","route","log","held messages","Settings"):
            check(w in note,f"says '{w}': {note}")
        check(len(note)<700,"short enough to read on a phone: %d"%len(note))
        await pg.locator("#sfOn").click(); await pg.wait_for_timeout(1500)
        check(all(g.cfg.get(k) is True for k in KEYS),"one tap turns every part on: %s"%{k:g.cfg.get(k) for k in KEYS})
        toast=await pg.locator("#toast").inner_text() if await pg.locator("#toast").count() else ""
        check("look after itself" in toast,"and says so: "+toast)
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(not await sec.is_visible(),"then it leaves the Overview")
        check(not await pg.locator("#autoUpdSec").is_visible(),"and so does the updates offer")
        # Not now, on a fresh set of answers
        g.apply_settings({k:False for k in KEYS if k!="auto_protect"}|{"set_forget_prompt":True,"auto_update_prompt":True})
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(await sec.is_visible(),"offered again once its parts are off and the offer is back")
        await pg.locator("#sfNo").click(); await pg.wait_for_timeout(1500)
        check(not any(g.cfg.get(k) for k in KEYS if k!="auto_protect"),"Not now turns nothing on")
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(not await sec.is_visible() and not await pg.locator("#autoUpdSec").is_visible(),"and both offers stay away")
        # where SpamGuard can't update itself, it isn't promised
        g.apply_settings({"set_forget_prompt":True}); sg.IN_PLUGIN=False
        save=sg.os.path.exists; sg.os.path.exists=lambda p: False if "openhop-spamguard-update" in str(p) else save(p)
        await pg.reload(); await pg.wait_for_timeout(2000)
        note=await pg.locator("#sfNote").inner_text()
        check("install by themselves" not in note,"no update promise where it can't update itself: "+note)
        sg.os.path.exists=save; sg.IN_PLUGIN=True
        await pg.set_viewport_size({"width":360,"height":800}); await pg.reload(); await pg.wait_for_timeout(2000)
        box=await sec.bounding_box()
        check(box and box["width"]<=360,"fits a small phone")
        on=await pg.locator("#sfOn").bounding_box()
        check(on and on["height"]>=24,"the button is big enough to tap")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
