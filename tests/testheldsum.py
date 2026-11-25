# The held messages summary: counts per day kept for about ten weeks, shown for the last 7 days, this month and last
# month, with counts only (no names, no message text). All data made up.
import sys, asyncio, time, json, calendar
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.mktime((2026,11,18,12,0,0,0,0,-1))
def day(y,mo,d): return time.strftime("%Y-%m-%d", time.localtime(time.mktime((y,mo,d,12,0,0,0,0,-1))))
g.daily.clear(); g.hist.clear()
g.daily[day(2026,11,17)]={"c":30,"fc":10,"kc":20,"kr":6,"rl":2,"bx":4}
g.daily[day(2026,11,2)]={"c":50,"fc":0,"kc":50,"rl":1,"bx":1}
g.daily[day(2026,10,30)]={"c":100,"fc":20,"kc":60,"kr":30,"rl":6,"bx":3}
g.daily[day(2026,9,30)]={"c":999}
hs=g.held_summary(now)
check(hs["week"]["held"]==40 and hs["week"]["released"]==2 and hs["week"]["share_released"]==5.0, f"the last 7 days: {hs['week']}")
check(hs["week"]["campaigns"]==20 and hs["week"]["routes"]==6 and hs["week"]["flood"]==10 and hs["week"]["other"]==4, "split by broad kind, the rest as other")
check(hs["month"]["held"]==90 and hs["month"]["expired"]==5, f"this calendar month: {hs['month']}")
check(hs["prev"]["held"]==120 and hs["prev"]["released"]==6, f"last month, in whole: {hs['prev']}")
check(hs["labels"]["month"]=="November 2026" and hs["labels"]["prev"]=="October 2026", f"month names: {hs['labels']}")
check(hs["week"]["held"]+hs["prev"]["held"]!=hs["month"]["held"], "months are by calendar, not rolling")
jan=g.held_summary(time.mktime((2027,1,5,9,0,0,0,0,-1)))
check(jan["labels"]["prev"]=="December 2026", "January's last month is December")
check(g.held_summary(now+0)["week"]["share_released"]==5.0 and g.held_summary(time.mktime((2026,12,25,0,0,0,0,0,-1)))["week"]["share_released"] is None, "no held messages: no share, not a divide by zero")
# counts from live traffic
g.daily.clear()
t=time.time()
g._day_bump(t,"c"); g._day_bump(t,"kc"); g._day_bump(t,"bx")
check(g.held_summary()["week"]["held"]==1 and g.held_summary()["week"]["expired"]==1, "counting bumps today")
check(g._day_kind({"kind":"text","source":"campaign"})=="kc" and g._day_kind({"kind":"hop","source":"hop"})=="kr" and g._day_kind({"kind":"lockdown"})=="ko", "kinds")
# ten weeks kept
for i in range(120): g.daily[day(2026,1,1)[:8]+"%02d"%(1+i%28)+str(i)]={"c":1}
g._day_bump(t,"c"); check(len(g.daily)<=g.DAILY_KEEP+11, f"old days are dropped: {len(g.daily)}")
# restarts keep it; the first run after an update fills days from the hourly history, totals only
g.daily.clear(); g.hist.clear()
hr=int(time.time())//3600*3600
g.hist[str(hr)]={"m":9,"c":4,"x":0,"g":0,"a":0.0,"h":{},"fc":3}
g._day_seed()
d0=g.daily[g._day_key(hr)]
check(d0["c"]==4 and d0["fc"]==3 and d0.get("seeded")==1, f"seeded from the hourly history: {d0}")
g._day_seed(); check(g.daily[g._day_key(hr)]["c"]==4, "and not twice")
g._save_state(force=True)
st=read_state(g.cfg["state_file"]) if os.path.exists(g.cfg["state_file"]+".gz") else {}
check("daily" in st and st["daily"], "saved with the rest of the state")
body=json.dumps(g.held_summary())
check(not any(k in body.lower() for k in ("sender","name","text","hilltop")), "the summary holds counts only")

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":390,"height":844})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        g.daily.clear(); g.daily[g._day_key(time.time())]={"c":412,"fc":86,"kc":293,"kr":28,"rl":9,"bx":31}
        await pg.goto("http://127.0.0.1:18171/"); await pg.wait_for_timeout(1500)
        check(await pg.is_visible("#heldSumSec"), "the card shows on the Overview")
        txt=await pg.text_content("#heldSumGrid")
        check("498" in txt and "9" in txt and "1.8%" in txt and "31" in txt, f"the figures: {txt}")
        rows=await pg.text_content("#heldSumGrid")   # 6.49: a doughnut with a legend of why, each with its number as text
        check("Spam campaigns" in rows and "293" in rows and "Flood control" in rows and "86" in rows and "Route blocks" in rows, "the split, with numbers as text")
        check(await pg.locator("#heldSumSec .donut").count()==1, "shown as a doughnut")
        check(await pg.get_attribute("#heldSumSec .donut","aria-label") and "Spam campaigns 293" in await pg.get_attribute("#heldSumSec .donut","aria-label"), "the doughnut is described, and the numbers are the text")
        check("not counted as right or wrong" in (await pg.text_content("#heldSumNote")), "it says what the share does not mean")
        await pg.click("#heldTabMonth"); await pg.wait_for_timeout(300)
        check(await pg.get_attribute("#heldTabMonth","aria-pressed")=="true" and "Covers" in (await pg.text_content("#heldSumNote")), "the month view")
        await pg.reload(); await pg.wait_for_timeout(1500)
        check(await pg.get_attribute("#heldTabMonth","aria-pressed")=="true", "the choice is remembered in this browser")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
