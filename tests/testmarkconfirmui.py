# An answer that goes against strong evidence is asked about in the browser first: cancelling changes nothing,
# confirming saves it. Made-up data only.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read().replace("18171","18196"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
import tempfile
ev=tempfile.mkdtemp(prefix="sg-mcui-"); now=time.time()
rows=[{"type":"msg","ts":now-2400,"sender":"Trail Runner 7","text":"Anyone fancy a run up the ridge tomorrow?","path":["C4","2F"],
       "channel":"#trailchat","caught_by":"hop:C4","caught_kind":"hop","caught_source":"hop","packet":"trpk"}]
with open(os.path.join(ev,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows))
g.file_cfg["evidence_log"]=True; g.file_cfg["evidence_dir"]=ev; g.rebuild_cfg()
g.mark_counts["Trail Runner 7"]=[2,0,now-3600]   # you marked two of this name's messages as spam before
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":412,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        asked=[]; answer=["dismiss"]
        async def on_dialog(d):
            asked.append(d.message); await (d.accept() if answer[0]=="accept" else d.dismiss())
        pg.on("dialog", lambda d: asyncio.ensure_future(on_dialog(d)))
        await pg.goto("http://127.0.0.1:18196/#/messages?f=held"); await pg.wait_for_timeout(1500)
        await pg.click("#qList [data-qi='0']"); await pg.wait_for_timeout(400)
        await pg.click("#qDetail button.go"); await pg.wait_for_timeout(1500)
        check(asked and "spam before" in asked[0], f"asked first: {asked}")
        check("Trail Runner 7" not in g.trust_on and g.mark_counts["Trail Runner 7"][1]==0, "cancelled: nothing changed")
        answer[0]="accept"; asked.clear()
        await pg.click("#qList [data-qi='0']") if await pg.query_selector("#qList [data-qi='0']") else None
        await pg.wait_for_timeout(300)
        await pg.check("#qTrust"); await pg.wait_for_timeout(100)   # 6.55: trust is its own choice
        await pg.click("#qList [data-qi='0']") if await pg.query_selector("#qList [data-qi='0']") else None
        await pg.wait_for_timeout(300)
        await pg.click("#qDetail button.go"); await pg.wait_for_timeout(1500)
        check(asked and g.trusted_here("Trail Runner 7","#trailchat"), "confirmed: saved and trusted on that channel")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
