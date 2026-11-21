# 6.45.0: a copied name on the People page (traffic-light directions, banner, filter) and the warmth bar, and the
# copy tag on Messages, in a browser with made-up demo data, light and dark, desktop and phone, with an axe scan.
import os, time, json
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18183"))
AXE=open(os.environ.get("AXE_JS", os.path.join(os.path.dirname(os.path.abspath(__file__)),".axe","node_modules","axe-core","axe.min.js"))).read()
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time()
g.apply_settings({"spoof_watch":True})
g.known["Moor Walker"]=[now-20*86400, now-240, 210]
g.dirs["moorwalker"]={"h":{"4A":40,"7C":38},"all":{"4A":40,"7C":38,"E1":30},"p":{"4A>7C":26,"5E>7C":24},"n":80,"last":now-300,
  "pend":{},"bad":["D2"],"auto":["D2"],"who":"Moor Walker",
  "copies":[[now-7200,"4A>D2>91","red",["device","new"]],[now-900,"4A>D2>33","red",["device","new","marked"]],[now-86400,"6B>F0>11","amber",["new"]]]}
g.blocks["imposter:demo1"]={"kind":"imposter","value":"D2","who":"Moor Walker","source":"spoof","created":now-7200,"expires":now+2*86400,"hits":3,"reason":"demo","channel":"Public"}
g.known["Lucky Prize"]=[now-2*86400, now-300, 6]; g.mark_counts["Lucky Prize"]=[3,0,now-5000]
e=sg.Event(now-900,["4A","D2","33"],"Moor Walker","made-up copied message","Public"); e.packet="cafe01"; e.copy={"level":"red","signs":["device","new"]}
g.events.append(e)
URL="http://127.0.0.1:18183/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme,vp in (("light",{"width":1280,"height":900}),("dark",{"width":1280,"height":900}),("light",{"width":320,"height":740})):
            ctx=await b.new_context(viewport=vp,color_scheme=scheme); pg=await ctx.new_page()
            errs=[]; pg.on("pageerror",lambda x:errs.append(str(x)))
            await pg.goto(URL+"#/people"); await pg.wait_for_timeout(1800)
            chip=pg.locator("#pplChips [data-ps=copied]")
            check(await chip.count()==1 and "1" in await chip.inner_text(),"a Name copied filter with its count")
            await chip.click(); await pg.wait_for_timeout(900)
            t=await pg.inner_text("#pplList")
            check("Moor Walker" in t and "Name copied" in t and "Someone else is probably using this name" in t,"the copied name shows a banner and a tag")
            check("D2" in t and "left" in t and "real person still gets through" in t,"the banner says where copies are held and for how long")
            m=await pg.evaluate("(()=>{const e=document.querySelector('#pplList .warm');return e&&[e.getAttribute('role'),e.getAttribute('aria-valuenow'),e.getAttribute('aria-valuetext')]})()")
            check(m and m[0]=="meter" and m[2].startswith("Looks genuine"),f"the warmth bar is a meter with words: {m}")
            await pg.click("#pplList summary"); await pg.wait_for_timeout(400)
            t=await pg.inner_text("#pplList")
            check("Where their messages come from" in t and "Usual" in t and "Probable copy" in t and "New direction" in t,"directions listed with their levels in words")
            check("a different device" in t,"the reason in words")
            await pg.add_script_tag(content=AXE)
            v=await pg.evaluate("""async()=>(await axe.run(document.getElementById('pplList'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
            check(not v,f"People with a copied name has no WCAG 2.1 AA problems ({scheme} {vp['width']}): {v}")
            check(await pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),f"no sideways scroll at {vp['width']}px")
            await pg.click("#pplChips [data-ps=active]"); await pg.wait_for_timeout(900)
            t=await pg.inner_text("#pplList")
            check("Worth a look" in t or "Probably spam" in t,"a name you marked as spam shows warmer")
            # Messages: the copy is tagged
            await pg.goto(URL+"#/messages"); await pg.wait_for_timeout(1500)
            await pg.click("#qChips [data-q=all]") if await pg.locator("#qChips [data-q=all]").count() else None
            await pg.wait_for_timeout(900)
            li=pg.locator("#qList > li:has-text('made-up copied message')")
            check(await li.count()>=1 and "Probably a copy" in await li.first.inner_text(),"the message is tagged as a probable copy")
            if await li.count() and vp["width"]>600:
                await li.first.locator(".q-open").click(); await pg.wait_for_timeout(400)
                d=await pg.inner_text("#qDetail")
                check("Probably a copy" in d and "different device" in d,"the message detail says why")
            check(not errs,f"no script errors: {errs}")
            await ctx.close()
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
