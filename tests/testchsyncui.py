# Every-channel blocks and the export/import controls in a browser, with made-up demo data.
import os, json
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18177"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g.apply_settings({"mode":"protect"})
g.action("mute",{"sender":"Zed Quill","channel":"Public","days":7})
URL="http://127.0.0.1:18177/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for vp in ({"width":1280,"height":900},{"width":320,"height":740}):
            ctx=await b.new_context(viewport=vp,accept_downloads=True); pg=await ctx.new_page()
            e=[]; pg.on("pageerror",lambda x:e.append(str(x)))
            await pg.goto(URL+"#/blocks"); await pg.wait_for_timeout(1500)
            sel=pg.locator("#blocks select[aria-label='Which channels']").first
            check(await sel.count()==1,"your mute has a channel picker")
            opts=await sel.evaluate("s=>[...s.options].map(o=>o.value)")
            check(sorted(opts[:-1])==["#trailchat","Public"] and opts[-1]=="*","choices: "+str(opts))
            if vp["width"]==1280:
                await sel.select_option("*"); await pg.wait_for_timeout(800)
                mute=[x for x in g.blocks.values() if x["kind"]=="burst" and x["value"]=="Zed Quill"]
                check(len(mute)==1 and mute[0]["channel"]=="*","choosing every channel moves the mute")
                txt=await pg.inner_text("#blocks")
                check("every channel" in txt,"the row says every channel")
                await pg.evaluate("localStorage.setItem('sgadv','1')"); await pg.goto(URL+"#/settings"); await pg.reload(); await pg.wait_for_timeout(1200)
                tc=await pg.eval_on_selector_all("#textChan option","os=>os.map(o=>o.value)")
                check("*" in tc,"adding a text block offers every channel")
                async with pg.expect_download() as dl:
                    await pg.click("#decExport")
                d=json.load(open(await (await dl.value).path()))
                check(d["format"]=="spamguard-decisions" and any(x["value"]=="Zed Quill" for x in d["blocks"]),"export downloads your blocks")
                g.blocks.clear()
                path=os.path.join(os.path.dirname(os.path.abspath(__file__)),".chsync-import.json"); json.dump(d,open(path,"w"))
                await pg.set_input_files("#decFile",path); await pg.wait_for_timeout(1200); os.remove(path)
                check(any(x["kind"]=="burst" and x["value"]=="Zed Quill" and x["channel"]=="*" for x in g.blocks.values()),"import brings it back")
                if os.environ.get("SHOT"):
                    await pg.goto(URL+"#/blocks"); await pg.wait_for_timeout(1000)
                    await pg.locator("#blocks").scroll_into_view_if_needed(); await pg.screenshot(path=os.environ["SHOT"])
            await pg.goto(URL+"#/channels"); await pg.wait_for_timeout(1000)
            box=pg.locator("#channels [data-chb='#trailchat']")
            check(await box.count()==1 and await box.is_checked() and await pg.is_visible("#crossRow"),"each channel has a Block spam here switch, and the follow-across option shows")
            if vp["width"]==1280:
                await box.uncheck(); await pg.wait_for_timeout(900)
                check("#trailchat" in g.watch_channels and "Read and counted only" in await pg.inner_text("#channels"),"switching it off makes the channel read-only")
                await pg.locator("#channels [data-chb='#trailchat']").check(); await pg.wait_for_timeout(900)
                check("#trailchat" not in g.watch_channels,"and on again")
            sw=await pg.evaluate("document.documentElement.scrollWidth<=innerWidth")
            check(sw,f"no sideways scroll at {vp['width']}px")
            check(not e,"no page errors "+str(e))
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
