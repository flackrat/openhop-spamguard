# The page on a weak connection: one refresh at a time, a slow or failed refresh keeps the last screen with a small
# note, "Not responding" only after several misses, no refreshing while the page is hidden, and big replies are
# compressed. Made-up demo data.
import os, asyncio
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18206"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
import urllib.request, gzip as _gz
r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:18206/status",headers={"Accept-Encoding":"gzip"}))
raw=r.read(); check(r.headers.get("Content-Encoding")=="gzip" and len(_gz.decompress(raw))>len(raw)*2,"status is sent compressed when the browser accepts it")
r=urllib.request.urlopen("http://127.0.0.1:18206/status"); check(r.headers.get("Content-Encoding") is None,"and plain when it doesn't")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(viewport={"width":390,"height":800})).new_page()
        calls={"n":0,"open":0,"max":0}; mode={"m":"ok"}
        async def handle(route):
            calls["n"]+=1; calls["open"]+=1; calls["max"]=max(calls["max"],calls["open"])
            try:
                if mode["m"]=="fail": await route.abort()
                elif mode["m"]=="slow":
                    await asyncio.sleep(12); await route.continue_()
                else: await route.continue_()
            finally: calls["open"]-=1
        await pg.route("**/status",handle)
        await pg.goto("http://127.0.0.1:18206/#/"); await pg.wait_for_timeout(2500)
        check("Loading" not in await pg.locator("#hero").inner_text(),"loads normally")
        mode["m"]="slow"; calls["max"]=0
        await pg.evaluate("load()"); await pg.wait_for_timeout(300); await pg.evaluate("load()"); await pg.evaluate("load()")
        await pg.wait_for_timeout(1000)
        check(calls["max"]<=1,"never more than one refresh at a time: %d"%calls["max"])
        await pg.wait_for_timeout(12000)
        for _ in range(60):   # a busy machine: let the slow refresh finish first
            if not calls["open"]: break
            await pg.wait_for_timeout(500)
        mode["m"]="fail"
        await pg.evaluate("load()")
        for _ in range(12):   # a slow CI machine: give the failed refresh time to come back
            await pg.wait_for_timeout(500)
            if await pg.locator("#connNote").is_visible(): break
        check(await pg.locator("#connNote").is_visible(),"one miss: a small note (misses %s)"%await pg.evaluate("load.misses"))
        check("Not responding" not in await pg.locator("#hPill").inner_text() and "Can't reach" not in await pg.locator("#hero").inner_text(),"and the last screen stays")
        for i in range(4): await pg.evaluate("load()"); await pg.wait_for_timeout(500)
        check("Can't reach" in await pg.locator("#hero").inner_text(),"several misses: Not responding")
        mode["m"]="ok"; await pg.evaluate("load()"); await pg.wait_for_timeout(1500)
        check(not await pg.locator("#connNote").is_visible() and "Can't reach" not in await pg.locator("#hero").inner_text(),"back to normal once it answers")
        n0=calls["n"]
        await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true})")
        await pg.evaluate("load()"); await pg.wait_for_timeout(500)
        check(calls["n"]==n0,"no refreshing while the page is hidden")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
