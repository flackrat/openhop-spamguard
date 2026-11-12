# The People page in a browser, at desktop and phone width, with a large made-up list.
import os, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18178"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time(); g.apply_settings({"known_min_msgs":3})
for i in range(240): g.known[f"{chr(65+i%26)}regular {i:03d}"]=[now-9*86400,now-600-i*60,15]
for i in range(150): g.known[f"newcomer {i:03d}"]=[now-3600,now-300-i*30,1]
g.known["Ann Hill"]=[now-12*86400,now-120,40]; g.homes["Ann Hill"]={"4C":30,"5E":8}; g.last_way["Ann Hill"]=[now-120,"E7>9B>2D"]
g.known["Loud Larry"]=[now-20*86400,now-200,47]; g.homes["Loud Larry"]={"C4":41,"9D":6}; g.last_way["Loud Larry"]=[now-200,"C4>2F"]
g.put_on_watch("Loud Larry","You said one of their messages was spam",now-2*86400); g.on_watch["Loud Larry"]["clean_from"]=now-2*86400
URL="http://127.0.0.1:18178/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for vp in ({"width":1280,"height":900},{"width":360,"height":740}):
            pg=await (await b.new_context(viewport=vp)).new_page()
            e=[]; pg.on("pageerror",lambda x:e.append(str(x)))
            await pg.goto(URL+"#/people"); await pg.evaluate("localStorage.setItem('sgadv','1')"); await pg.reload(); await pg.wait_for_timeout(1800)
            check(await pg.is_visible("nav a[data-nav='people']") or vp["width"]<700,"People is in the menu")
            rows=await pg.locator("#pplList > li").count()
            check(rows==20,f"one screenful of names, not all of them ({rows})")
            first=await pg.inner_text("#pplList > li >> nth=0")
            check("Loud Larry" in first and "On watch" in first and "normal days" in first,"a name on watch is first, with its progress")
            chips=await pg.inner_text("#pplChips")
            check("Active" in chips and "On watch" in chips and "Learning" in chips and "Not heard lately" in chips,"filters with counts")
            check("newcomer" not in await pg.inner_text("#pplList"),"names still being learnt are not in the everyday list")
            await pg.fill("#pplFind","ann hi"); await pg.wait_for_timeout(900)
            t=await pg.inner_text("#pplList")
            check("Ann Hill" in t and "not a way in they normally use" in t and await pg.locator("#pplList > li").count()==1,"search finds a name, and its unusual route is flagged")
            await pg.click("#pplList summary"); await pg.wait_for_timeout(300)
            body=await pg.inner_text("#pplList .ppl-body")
            check("Heard via" in body and "4C" in body and "Put on watch" in body and "Forget" in body,"opening a name shows where it is heard from and what you can do")
            if vp["width"]==1280:
                await pg.click("#pplList .ppl-body button:has-text('Put on watch')"); await pg.wait_for_timeout(1200)
                check("Ann Hill" in g.on_watch,"Put on watch works")
                await pg.wait_for_timeout(3500)
                await pg.click("#pplList .ppl-body button:has-text('Take off watch')"); await pg.wait_for_timeout(1200)
                check("Ann Hill" not in g.on_watch,"and Take off watch")
            await pg.fill("#pplFind",""); await pg.wait_for_timeout(700)
            await pg.select_option("#pplSort","name"); await pg.wait_for_timeout(900)
            check(await pg.is_visible("#pplIndex") and await pg.locator("#pplIndex button").count()>=20,"A to Z shows a letter index")
            await pg.click("#pplIndex button:has-text('M')"); await pg.wait_for_timeout(900)
            check((await pg.inner_text("#pplList > li >> nth=0")).strip().upper().startswith("M"),"choosing a letter jumps to it")
            await pg.click("#pplMoreBtn"); await pg.wait_for_timeout(900)
            check(await pg.locator("#pplList > li").count()==40,"Show more adds the next screenful")
            await pg.click("[data-ps=learning]"); await pg.wait_for_timeout(900)
            check("newcomer" in await pg.inner_text("#pplList") and "dropped" in await pg.inner_text("#pplAge"),"Learning lists the newcomers, and the page says they age out")
            check(await pg.evaluate("document.documentElement.scrollWidth<=innerWidth"),f"no sideways scroll at {vp['width']}px")
            await pg.goto(URL+"#/exceptions"); await pg.wait_for_timeout(800)
            check("#/people" in pg.url,"the old Exceptions link opens People")
            await pg.goto(URL+"#/blocks"); await pg.wait_for_timeout(800)
            check(await pg.locator("#neverBox").count()==1 and not await pg.is_visible("#trustTexts"),"Never blocked sits on Blocks, closed until opened")
            if os.environ.get("SHOT") and vp["width"]==360:
                await pg.goto(URL+"#/people"); await pg.wait_for_timeout(1500); await pg.click("#pplList summary"); await pg.wait_for_timeout(300)
                await pg.screenshot(path=os.environ["SHOT"],full_page=True)
            check(not e,"no page errors "+str(e))
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
