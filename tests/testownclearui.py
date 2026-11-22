# Old values of your own that override the protection level: pointed out under the level, with a button that asks
# first and then clears them so the level (and Auto level) is in charge again. Values from the config file are only
# mentioned, as the page can't change them. Made-up demo data.
import os, asyncio
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18201"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g.apply_settings({"set_forget_prompt":False})
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        asked=[]; answer=["dismiss"]
        async def dlg(d):
            asked.append(d.message); await (d.accept() if answer[0]=="accept" else d.dismiss())
        pg.on("dialog",lambda d: asyncio.ensure_future(dlg(d)))
        await pg.goto("http://127.0.0.1:18201/#/"); await pg.wait_for_timeout(2000)
        check(not await pg.locator("#lvlOwnClear").count(),"nothing to clear: no button")
        g.apply_settings({"slow_repeat_max":5,"level_auto":True}); await pg.reload(); await pg.wait_for_timeout(2000)
        btn=pg.locator("#lvlOwnClear")
        check(await btn.is_visible(),"an old value of yours: the button is offered")
        check("Auto level can't change these" in await pg.locator("#lvlOwn").inner_text(),"and it says Auto level can't touch them")
        await btn.click(); await pg.wait_for_timeout(1200)
        check(asked and "Clear your own values" in asked[0],"it asks first")
        check(g.settings.get("slow_repeat_max")==5,"No keeps your value")
        answer[0]="accept"; await btn.click(); await pg.wait_for_timeout(1800)
        check("slow_repeat_max" not in g.settings,"Yes clears it")
        check(g.cfg.get("level_auto") is True,"and leaves Auto level as it was")
        toast=await pg.locator("#toast").inner_text()
        check("level's values are used" in toast,"and says so: "+toast)
        check(not await pg.locator("#lvlOwnClear").count(),"then the button goes")
        g.file_cfg["slow_repeat_max"]=4; g.rebuild_cfg(); await pg.reload(); await pg.wait_for_timeout(2000)
        check("your own setting" in await pg.locator("#lvlOwn").inner_text() and not await pg.locator("#lvlOwnClear").count(),
              "a value from the config file is pointed out, without a button the page can't honour")
        g.file_cfg.pop("slow_repeat_max",None); g.rebuild_cfg()
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
