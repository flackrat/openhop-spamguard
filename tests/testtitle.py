# The browser tab names the repeater, so several SpamGuards open at once can be told apart, and the owner can
# give it a name of their own. Made-up demo data.
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18193"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
# The name is read from where openHop really reports it (its stats, under config)
real_api=g._api
def api(method,path,body=None,**k):
    if path=="/api/stats": return {"success":True,"data":{"local_hash":"a1","config":{"node_name":"Hill Top Repeater","radio":{},"repeater":{"mode":"forward","latitude":0,"longitude":0}}}}
    return real_api(method,path,body,**k)
g._api=api; g.me={}; g.repeaters["ts"]=0
try: g.refresh_openhop_info(force=True)
except TypeError: g.refresh_openhop_info()
g._api=real_api; g.repeaters["ts"]=time.time()+1e9
check(g.me.get("name")=="Hill Top Repeater","the name is read from openHop's own stats: "+str(g.me.get("name")))
check(g.status()["site"]=="Hill Top Repeater","and reaches the page")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:18193/#/"); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t.startswith("Hill Top Repeater · SpamGuard · Overview"),"title: "+t)
        await pg.goto("http://127.0.0.1:18193/#/messages"); await pg.wait_for_timeout(1200)
        t=await pg.title(); check(t=="Hill Top Repeater · SpamGuard · Messages","follows the page: "+t)
        g.apply_settings({"site_label":"  Shed\tPi  "})
        await pg.reload(); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t=="Shed Pi · SpamGuard · Messages","a name of your own wins: "+t)
        g.apply_settings({"site_label":"x"*90}); check(len(g.cfg["site_label"])==40,"kept short")
        g.apply_settings({"site_label":"<img src=x onerror=alert(1)>"})
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(await pg.title()=="<img src=x onerror=alert(1)> · SpamGuard · Messages" and await pg.locator("img[src=x]").count()==0,"shown as text, never run")
        g.apply_settings({"site_label":""})
        await pg.reload(); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t=="Hill Top Repeater · SpamGuard · Messages","cleared: back to openHop's name: "+t)
        await pg.evaluate("openSettings('browser tab')"); await pg.wait_for_timeout(900)
        check(await pg.locator("input[data-k='site_label']").count()==1,"the setting has a text box")
        g.me={}
        await pg.reload(); await pg.wait_for_timeout(2000)
        t=await pg.title(); check(t.startswith("SpamGuard · "),"no name known: plain title: "+t)
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
