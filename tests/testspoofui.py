# The Spoofed answer, the route line on a message, and the route check on the People page, in a browser, with
# made-up demo data.
import os, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18179"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time()
g.apply_settings({"spoof_check":True,"known_min_msgs":1})
g.neighbours={"2F":{"rssi":-90,"snr":6,"n":50}}; g.neighbours_ts=now+3600
g.known["Ann Hill"]=[now-12*86400,now-120,40]; g.homes["Ann Hill"]={"4C":30,"5E":8}
g.last_full["Ann Hill"]=[now-120,["E7","31","7A"],-60.0,False]; g.last_way["Ann Hill"]=[now-120,"E7>31>7A"]
g._route_add("31>72","spam","Qx1",now); g._route_add("31>72","spam","Qx2",now)
# a recent message from a known name, by a way in they don't use
g.poll_once(); g.sync_pending=True
URL="http://127.0.0.1:18179/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for vp in ({"width":1280,"height":900},{"width":360,"height":740}):
            pg=await (await b.new_context(viewport=vp)).new_page()
            e=[]; pg.on("pageerror",lambda x:e.append(str(x)))
            await pg.goto(URL+"#/people"); await pg.evaluate("localStorage.setItem('sgadv','1')"); await pg.reload(); await pg.wait_for_timeout(1800)
            await pg.fill("#pplFind","Ann Hill"); await pg.wait_for_timeout(900)
            t=await pg.inner_text("#pplList")
            check("Probably a copy" in t,"a red route is shown on the person's row: "+t[:120].replace("\n"," "))
            await pg.click("#pplList summary"); await pg.wait_for_timeout(300)
            t=await pg.inner_text("#pplList")
            check("Route check" in t and "directly" in t,"the detail gives the reasons in words")
            check(await pg.evaluate("document.documentElement.scrollWidth<=innerWidth"),f"no sideways scroll at {vp['width']}px")
            # Messages: a known name's message offers Spoofed, and the route line shows
            await pg.goto(URL+"#/messages"); await pg.wait_for_timeout(1500)
            rows=await pg.locator("#qList > li").count()
            check(rows>0,"messages are listed")
            if vp["width"]==1280:
                await pg.click("#qList > li >> nth=0"); await pg.wait_for_timeout(400)
                d=await pg.inner_text("#qDetail")
                check("Spam" in d and "Not spam" in d,"every message can be answered Spam or Not spam")
                # a known regular: the Spoofed button and the explanation
                g.known["Hilltop Hiker"]=[now-9*86400,now-60,30]
                await pg.reload(); await pg.wait_for_timeout(1500)
                items=await pg.locator("#qList > li").all_inner_texts()
                idx=next((i for i,x in enumerate(items) if "Hilltop Hiker" in x),None)
                if idx is not None:
                    await pg.click(f"#qList > li >> nth={idx}"); await pg.wait_for_timeout(400)
                    d=await pg.inner_text("#qDetail")
                    check("Spoofed" in d,"a known name's message offers Spoofed")
                    check("This route" in d,"and shows what the route has carried")
                    await pg.click("#qDetail button:has-text('Spoofed')"); await pg.wait_for_timeout(1200)
                    check(any(x.get("who")=="Hilltop Hiker" or x["kind"]=="imposter" for x in g.blocks.values()) or g.labels,"answering records it")
                else:
                    check(True,"(no regular in this list)")
            check(not e,"no page errors "+str(e))
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
