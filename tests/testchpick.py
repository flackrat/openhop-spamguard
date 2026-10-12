# The Overview's channel picker in a browser, with made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for vp in ({"width":1280,"height":900},{"width":320,"height":740}):
            pg=await (await b.new_context(viewport=vp)).new_page()
            e=[]; pg.on("pageerror",lambda x:e.append(str(x)))
            await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(1500)
            check(await pg.is_visible("#chSel"),"picker shown with two channels")
            opts=await pg.eval_on_selector_all("#chSel option","os=>os.map(o=>o.textContent)")
            check(opts==["All channels","Public","#trailchat"],"options: "+str(opts))
            lab=lambda: pg.get_attribute("#chart24","aria-label")
            all24=await lab()
            await pg.select_option("#chSel","#trailchat"); await pg.wait_for_timeout(300)
            one=await lab()
            check("on #trailchat" in one and one!=all24,"chart label follows the picker: "+one[:60])
            rows=await pg.eval_on_selector_all("#chart24 ~ details tr, #chart24 + details tr","r=>r.length")
            await pg.reload(); await pg.wait_for_timeout(1500)
            check(await pg.input_value("#chSel")=="#trailchat","choice remembered")
            sw=await pg.evaluate("document.documentElement.scrollWidth<=innerWidth")
            check(sw,f"no sideways scroll at {vp['width']}px")
            if vp["width"]==1280:
                await pg.select_option("#chSel","Public"); await pg.wait_for_timeout(300)
                await pg.locator("#chPick").scroll_into_view_if_needed()
                await pg.screenshot(path=os.environ.get("SHOT","/dev/null") if os.environ.get("SHOT") else "/tmp/_chpick.png",full_page=False)
            await pg.select_option("#chSel",""); await pg.wait_for_timeout(200)
            check(await lab()==all24,"All channels restores the totals")
            check(not e,"no page errors "+str(e))
        # with one channel only the picker hides
        g.extra_channels.clear(); g.rebuild_cfg()
        for v in g.hist.values(): v.get("ch",{}).pop("#trailchat",None)
        pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(1500)
        check(await pg.is_hidden("#chPick"),"picker hidden with one channel")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
