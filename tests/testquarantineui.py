# The message list in the browser: the Overview's numbers open it already filtered, the filters show their
# counts, a message opens with why and what can be done, and actions reach SpamGuard. Made-up data only.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
import tempfile
ev=tempfile.mkdtemp(prefix="sg-qui-"); now=time.time(); rows=[]
for i in range(5): rows.append({"type":"msg","ts":now-600-i*20,"sender":f"RND{i}XQZ7","text":"FREE PRIZE claim now at spam.example/win","path":["C4","9D"],"channel":"Public","caught_by":"text:a","caught_kind":"text","caught_source":"dedupe","random":True})
rows.append({"type":"msg","ts":now-2400,"sender":"Trail Runner 7","text":"Anyone fancy a run up the ridge tomorrow?","path":["C4","2F"],"channel":"#trailchat","caught_by":"hop:C4","caught_kind":"hop","caught_source":"hop","packet":"trpk"})
rows.append({"type":"msg","ts":now-900,"sender":"Hilltop Hiker","text":"Morning all, clear skies up here","path":["A7","2F"],"channel":"Public","known":True,"packet":"hhpk"})
with open(os.path.join(ev,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows))
g.file_cfg["evidence_log"]=True; g.file_cfg["evidence_dir"]=ev; g.rebuild_cfg()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        posts=[]; pg.on("request",lambda r: posts.append((r.url.rsplit("/",1)[-1],r.post_data)) if r.method=="POST" else None)
        await pg.goto("http://127.0.0.1:18171/"); await pg.wait_for_timeout(1500)
        links=await pg.evaluate("[...document.querySelectorAll('#kpis a.tile-go')].map(a=>a.getAttribute('href'))")
        check("#/messages?f=stopped" in links and "#/messages?f=held" in links and "#/messages?f=letthrough" in links, f"the Overview's numbers are links to the list: {links}")
        await pg.click("#kpis a[href='#/messages?f=held']"); await pg.wait_for_timeout(1500)
        check(await pg.is_visible("#qSec"), "clicking a number opens the message list")
        pressed=await pg.evaluate("document.querySelector('#qChips [aria-pressed=true]').dataset.q")
        rows_t=await pg.text_content("#qList")
        check(pressed=="held" and "Trail Runner 7" in rows_t and "FREE PRIZE" not in rows_t, f"already filtered to what was clicked: {pressed}")
        chips=await pg.text_content("#qChips")
        check("Stopped 5" in chips.replace("\xa0"," ") or "Stopped5" in chips.replace(" ",""), f"every filter shows its count: {chips}")
        await pg.click("#qList [data-qi='0']"); await pg.wait_for_timeout(400)
        det=await pg.text_content("#qDetail")
        check("burst of made-up names" in det and "Let it through" in det, "a message opens with why, and what can be done")
        await pg.click("#qDetail button.go"); await pg.wait_for_timeout(1500)
        check(any(u=="not_spam" and "Trail Runner 7" in (d or "") for u,d in posts), "Let it through tells SpamGuard")
        check("Trail Runner 7" in g.allow_senders, "and the sender is trusted from then on")
        await pg.click("[data-q=all]"); await pg.wait_for_timeout(1200)
        t=await pg.text_content("#qList")
        check("×5" in t, "copies of one message are grouped")
        await pg.fill("#qFind","clear skies"); await pg.wait_for_timeout(1500)
        t=await pg.text_content("#qList")
        check("Hilltop Hiker" in t and "FREE PRIZE" not in t, "search narrows the list")
        await pg.fill("#qFind",""); await pg.wait_for_timeout(1200)
        boxes=await pg.query_selector_all("#qList input[type=checkbox]")
        await boxes[0].check(); await pg.wait_for_timeout(300)
        check(await pg.is_visible("#qBulk"), "ticking messages offers actions for all of them")
        await pg.click("#qBulk [data-qb=spam]"); await pg.wait_for_timeout(1500)
        check(any(u=="label" for u,_ in posts), "a label for the ticked messages reaches SpamGuard")
        # phone: no sideways scrolling
        ph=await b.new_page(viewport={"width":390,"height":844})
        await ph.goto("http://127.0.0.1:18171/#/messages?f=all"); await ph.wait_for_timeout(1800)
        wide=await ph.evaluate("document.documentElement.scrollWidth>window.innerWidth+1")
        check(not wide, "on a phone the list fits without sideways scrolling")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
