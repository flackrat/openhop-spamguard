# People on a phone: the main filter chips, the rarer ones under More, the "Most likely spam first" order, and the
# choices remembered on this browser. Made-up demo data.
import os, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18202"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time()
g.cfg["spoof_watch"]=True
for i,n in enumerate(["Quarry Pete","Canal Boat Ted","Hilltop Mo","Visitor Q7"]):
    g.known[n]=[now-9*86400, now-60*(i+1), 20]
g.dirs[g.name_family("Canal Boat Ted")]={"who":"Canal Boat Ted","h":{},"all":{},"p":{},"n":30,"last":now,"pend":{},"bad":[],"auto":[],"dd":[1,2],
    "copies":[[now-3600,"7A>2B","amber",["new"]]]}
g.mark_counts["Visitor Q7"]=[3,0,now]; g.mark_counts["Hilltop Mo"]=[1,2,now]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(viewport={"width":360,"height":800}); pg=await ctx.new_page()
        await pg.goto("http://127.0.0.1:18202/#/people"); await pg.wait_for_timeout(2500)
        main_chips=[await x.inner_text() for x in await pg.locator("#pplChips > button.q-chip").all()]
        check(len(main_chips)==6 and any("Worth a look" in t for t in main_chips) and any("Check the route" in t for t in main_chips),"six main chips: %s"%main_chips)
        check(all(any(ch.isdigit() for ch in t) for t in main_chips),"each with its count")
        more=pg.locator("#pplMoreChips")
        check(not await more.evaluate("e=>e.open"),"the rarer ones are folded under More")
        check(not await pg.locator("#pplMoreChips button[data-ps=marked]").is_visible(),"and hidden until opened")
        await pg.locator("#pplMoreChips > summary").click(); await pg.wait_for_timeout(300)
        check(await pg.locator("#pplMoreChips button[data-ps=marked]").is_visible(),"More opens them")
        await pg.locator("#pplMoreChips button[data-ps=marked]").click(); await pg.wait_for_timeout(1500)
        names=[await x.get_attribute("data-pn") for x in await pg.locator("#pplList details[data-pn]").all()]
        check(sorted(names)==["Hilltop Mo","Visitor Q7"],"Marked spam by you lists them: %s"%names)
        await pg.select_option("#pplSort","warmth"); await pg.wait_for_timeout(1500)
        names=[await x.get_attribute("data-pn") for x in await pg.locator("#pplList details[data-pn]").all()]
        check(names[:1]==["Visitor Q7"],"Most likely spam first puts the hottest at the top: %s"%names)
        await pg.reload(); await pg.wait_for_timeout(2500)
        check(await pg.input_value("#pplSort")=="warmth","the order is remembered")
        check(await more.evaluate("e=>e.open") and await pg.locator("#pplMoreChips button[data-ps=marked]").get_attribute("aria-pressed")=="true","and the filter, with More open to show it")
        await pg.locator("#pplChips button[data-ps=check]").click(); await pg.wait_for_timeout(1500)
        names=[await x.get_attribute("data-pn") for x in await pg.locator("#pplList details[data-pn]").all()]
        check(names==["Canal Boat Ted"],"Check the route: %s"%names)
        await pg.locator("#pplChips button[data-ps=worth]").click(); await pg.wait_for_timeout(1500)
        check(await pg.locator("#pplChips button[data-ps=worth]").get_attribute("aria-pressed")=="true","chips say which is chosen")
        sw=await pg.evaluate("document.documentElement.scrollWidth")
        check(sw<=360,"nothing runs off a small phone: %d"%sw)
        h=await pg.locator("#pplMoreChips > summary").bounding_box()
        check(h and h["height"]>=36,"More is as easy to tap as the chips")
        g.mark_counts.clear(); await pg.evaluate("store.set('sgPplShow','mixed')"); await pg.reload(); await pg.wait_for_timeout(2500)
        check("No name has marks both ways" in await pg.locator("#pplList").inner_text(),"an empty filter says so in words")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
