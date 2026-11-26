# The busiest-channels list: how many to show, sort order and which kind, each remembered; bot channels tagged;
# the Protect button reads the channel; switching blocking on for a bot channel asks first. Made-up channels.
import sys, os, asyncio, random
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
random.seed(5); now=time.time()
spec=[("Public",600),("#ping",150),("#bot",120),("#ridgeline",50),(None,30),("#weather",25),("#quarrychat",10),("#valleynet",2)]
for i,(name,avg) in enumerate(spec):
    days={time.strftime("%Y-%m-%d",time.localtime(now-d*86400)):[avg,max(1,avg//8),[]] for d in range(10)}
    g.chan_heard[f"n:{name}" if name else "h:e0"]={"name":name,"hash":0xE0 if not name else i,"first":now-9*86400,"last":now-60*(i+1),"days":days}
g._chh_cache=None
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1000,"height":1000})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:18171/#/channels"); await pg.wait_for_timeout(2000)
        names=lambda: pg.eval_on_selector_all("#chHeard .ch-main b","els=>els.map(e=>e.textContent)")
        n=await names(); check(len(n)==8 and n[0]=="Public" and n[-1]=="#trailchat" and not any(x.startswith("Unnamed") for x in n),"unnamed hidden at first; the others busiest first, with a read channel not heard yet at the end: %s"%n)
        check("1 unnamed hidden" in await pg.text_content("#chTopNote"),"and it says how many are hidden")
        await pg.check("#chUnnamed"); await pg.wait_for_timeout(200)
        n=await names(); check(len(n)==9 and await pg.is_visible("#chUnnamedNote"),"Show unnamed brings it back, with a line on why it has no name: %s"%n)
        await pg.select_option("#chTop","5"); await pg.wait_for_timeout(200)
        check(len(await names())==5 and "Showing 5 of 9" in await pg.text_content("#chTopNote"),"top 5 shows five and says so")
        await pg.select_option("#chSort","name"); await pg.wait_for_timeout(200)
        n=await names(); check(n==sorted(n,key=str.lower) or n[0].startswith("#"),"sorted by name: %s"%n)
        await pg.select_option("#chKind","bots"); await pg.wait_for_timeout(200)
        n=await names(); check(set(n)<={"#ping","#bot","#weather"} and len(n)==3,"bots and tests only: %s"%n)
        check(await pg.locator("#chHeard .tag.would").count()==3,"each tagged mostly bots")
        await pg.reload(); await pg.wait_for_timeout(1800)
        check(await pg.input_value("#chKind")=="bots" and await pg.input_value("#chSort")=="name" and await pg.input_value("#chTop")=="5","choices remembered after a reload")
        await pg.select_option("#chKind","found"); await pg.wait_for_timeout(200)
        btn=pg.locator('[data-chprotect="#ridgeline"]'); check(await btn.count()==1 and (await btn.text_content())=="Protect","an ordinary found channel offers Protect")
        await btn.click(); await pg.wait_for_timeout(1500)
        check("#ridgeline" in g.cfg["channels"],"Protect makes SpamGuard read it")
        b2=pg.locator('[data-chprotect="#weather"]'); check((await b2.text_content())=="Protect, bot-safe","a bot channel offers bot-safe protection")
        await b2.click(); await pg.wait_for_timeout(1500)
        check("#weather" in g.cfg["channels"] and "#weather" in g.botsafe_channels,"and it is protected bot-safe")
        # switching blocking on for it asks first; saying no changes nothing
        check(await pg.input_value('[data-chb="#weather"]')=="botsafe","the channel list shows it as bot-safe")
        pg.once("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        await pg.select_option('[data-chb="#weather"]',"full"); await pg.wait_for_timeout(1500)
        check("#weather" in g.botsafe_channels,"declining the question changes nothing")
        check(await pg.input_value('[data-chb="#weather"]')=="botsafe","and the choice goes back")
        pg.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.select_option('[data-chb="#weather"]',"full"); await pg.wait_for_timeout(1500)
        check("#weather" not in g.botsafe_channels,"confirming switches full blocking on")
        await pg.select_option('[data-chb="#weather"]',"watch"); await pg.wait_for_timeout(1500)
        check("#weather" in g.watch_channels,"count only can be chosen without a question")
        check(not errs,f"no page errors {errs}")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); os._exit(1 if fail else 0)
