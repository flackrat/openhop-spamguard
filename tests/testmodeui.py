# Leaving Protect asks first, in the page; a banner on every page says nothing is held while not in Protect;
# the Auto tick box tucks away once chosen; a notice says when no page password is set. Made-up data only.
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
        pg=await b.new_page(viewport={"width":390,"height":844})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        dialogs=[]; pg.on("dialog",lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.dismiss())))
        await pg.goto("http://127.0.0.1:18171/"); await pg.wait_for_timeout(1500)
        g.apply_settings({"mode":"protect","paused":False}); await pg.evaluate("load(true)"); await pg.wait_for_timeout(600)
        check(not await pg.query_selector("#modeWarn"), "no banner while protecting")
        # no page password: a notice, and it can be dismissed
        check(await pg.is_visible("#pwHint") and "change SpamGuard's settings" in (await pg.text_content("#pwHint")), "a notice says no page password is set")
        await pg.click("#pwHint button"); await pg.wait_for_timeout(200)
        await pg.evaluate("load(true)"); await pg.wait_for_timeout(600)
        check(not await pg.query_selector("#pwHint"), "and stays dismissed")
        # leaving Protect asks first
        await pg.click("#modeSeg button[data-v=monitor]"); await pg.wait_for_timeout(300)
        check(await pg.is_visible("#modeConfirm") and g.cfg["mode"]=="protect", "pressing Monitor asks first and changes nothing yet")
        check("blocks nothing" in (await pg.text_content("#modeConfirmTxt")), "and says what Monitor means")
        check(await pg.evaluate("document.activeElement.id")=="modeConfirmStay", "focus starts on the safe choice")
        await pg.click("#modeConfirmStay"); await pg.wait_for_timeout(300)
        check(not await pg.is_visible("#modeConfirm") and g.cfg["mode"]=="protect", "Stay in Protect changes nothing")
        await pg.click("#modeSeg button[data-v=pause]"); await pg.wait_for_timeout(300)
        check("lifts every" in (await pg.text_content("#modeConfirmTxt")), "Pause asks too")
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)
        check(not await pg.is_visible("#modeConfirm") and g.cfg["mode"]=="protect", "Escape closes it without changing anything")
        await pg.click("#modeSeg button[data-v=monitor]"); await pg.wait_for_timeout(300)
        await pg.click("#modeConfirmGo"); await pg.wait_for_timeout(1500)
        check(g.cfg["mode"]=="monitor", "confirming switches to Monitor")
        check(await pg.is_visible("#modeWarn") and "nothing is being held" in (await pg.text_content("#modeWarn")), "a banner says nothing is held")
        await pg.evaluate("location.hash='#/settings'"); await pg.wait_for_timeout(500)
        check(await pg.is_visible("#modeWarn"), "and it shows on the other pages too")
        check(await pg.get_attribute("#modeWarn","role")=="status" and not await pg.query_selector("#modeWarn [aria-label*=ismiss]"), "it is announced and can't be dismissed for good")
        await pg.evaluate("location.hash='#/overview'"); await pg.wait_for_timeout(400)
        await pg.click("#modeSeg button[data-v=pause]"); await pg.wait_for_timeout(1500)
        check(g.cfg.get("paused") is True and not await pg.is_visible("#modeConfirm"), "Monitor to Pause needs no question")
        check("paused" in (await pg.text_content("#modeWarn")), "the banner says paused")
        await pg.click("#modeWarn button"); await pg.wait_for_timeout(1500)
        check(g.cfg["mode"]=="protect" and g.cfg.get("paused") is False and not await pg.query_selector("#modeWarn"), "one press on the banner returns to Protect")
        check(not dialogs, f"no browser dialogs were used: {dialogs}")
        # Auto: its own switch only when "Look after itself" was turned down and Auto is off (6.49)
        g.apply_settings({"level_auto":False,"set_forget_prompt":False}); await pg.evaluate("load(true)"); await pg.wait_for_timeout(800)
        check(await pg.is_visible("#lvlAuto"), "Look after itself turned down and Auto off: its switch shows")
        await pg.click("#lvlAuto"); await pg.wait_for_timeout(1800)
        check(g.cfg.get("level_auto") is True, "ticking it turns Auto on")
        check(await pg.is_hidden("#autoPart"), "once on, the switch goes")
        check("Moves by itself" in (await pg.text_content("#lvlAutoLine")) and await pg.is_visible("#lvlAutoLine"), "leaving one line under the slider")
        g.apply_settings({"level_auto":False,"set_forget_prompt":True}); await pg.evaluate("load(true)"); await pg.wait_for_timeout(800)
        if (g.status_now().get("set_forget") or {}).get("offer"):
            check(await pg.is_hidden("#autoPart") and await pg.is_visible("#sfOn"), "while Look after itself is offered, that one button covers it")
        # the level's description is under the existing fold-away
        check(not await pg.is_visible("#sensExplain"), "the level's description is folded away too")
        await pg.evaluate("document.querySelector('#lvlMore').open=true"); await pg.wait_for_timeout(200)
        check(await pg.is_visible("#sensExplain"), "and appears when that is opened")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
