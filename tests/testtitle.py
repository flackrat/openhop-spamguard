# The browser tab names the repeater, so several SpamGuards open at once can be told apart. Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18193"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
check(g.status()["site"]=="" or isinstance(g.status()["site"],str),"status carries the repeater name")
g.me={"name":"Hill Top Repeater"}
check(g.status()["site"]=="Hill Top Repeater","the name comes from openHop")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18193/#/"); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t.startswith("Hill Top Repeater · SpamGuard · Overview"),"title: "+t)
        await pg.goto("http://127.0.0.1:18193/#/messages"); await pg.wait_for_timeout(1200)
        t=await pg.title(); check(t=="Hill Top Repeater · SpamGuard · Messages","follows the page: "+t)
        g.me={}
        await pg.reload(); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t=="SpamGuard · Messages","no name known: plain title: "+t)
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
