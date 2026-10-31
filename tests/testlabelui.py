# A message you label stays visibly labelled: the list shows "Marked spam by you" on it, and the message itself
# says when you did it. Clearing the label removes both, and labels and their times survive a restart.
import sys, os, time, asyncio, json, tempfile
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
ev=tempfile.mkdtemp(prefix="sg-lab-"); now=time.time()
rows=[{"type":"msg","ts":now-900,"sender":"Loud Larry","text":"Visit my totally great page today everyone","path":["C4","2F"],"channel":"Public","packet":"llpk1"},
      {"type":"msg","ts":now-800,"sender":"Hilltop Hiker","text":"Morning all, clear skies up here","path":["A7","2F"],"channel":"Public","known":True,"packet":"hhpk1"}]
with open(os.path.join(ev,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows))
g.file_cfg["evidence_log"]=True; g.file_cfg["evidence_dir"]=ev; g.rebuild_cfg()
r=g.action("label",{"label":"spam","sender":"Loud Larry","text":rows[0]["text"],"packet":"llpk1"})
check("Labelled as spam" in str(r.get("message")), "labelling answers")
check(g.label_at.get("llpk1") and abs(g.label_at["llpk1"]-time.time())<5, "the time of the label is kept")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            pg=await (await b.new_context(viewport={"width":1280,"height":900},color_scheme=scheme)).new_page()
            errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
            await pg.goto("http://127.0.0.1:18171/#/messages?f=all"); await pg.wait_for_timeout(1800)
            lst=await pg.text_content("#qList")
            check("Marked spam by you" in lst, f"{scheme}: the list shows the label on the message")
            items=await pg.eval_on_selector_all("#qList li","ls=>ls.map(l=>l.textContent)")
            check(sum("Marked" in t for t in items)==1, "only the labelled message carries it")
            idx=next(i for i,t in enumerate(items) if "Loud Larry" in t)
            await pg.click(f"#qList [data-qi='{idx}']"); await pg.wait_for_timeout(400)
            det=await pg.text_content("#qDetail")
            check("You marked this as spam on" in det, f"the message says when you labelled it: {det[:160]}")
            check(not errs, "no page errors "+str(errs))
        # clearing removes it
        g.action("label",{"label":"none","sender":"Loud Larry","text":rows[0]["text"],"packet":"llpk1"})
        pg=await (await b.new_context(viewport={"width":1280,"height":900})).new_page()
        await pg.goto("http://127.0.0.1:18171/#/messages?f=all"); await pg.wait_for_timeout(1800)
        check("Marked spam by you" not in await pg.text_content("#qList"), "clearing the label removes it")
        await b.close()
asyncio.run(main())
g.action("label",{"label":"spam","sender":"Loud Larry","text":rows[0]["text"],"packet":"llpk1"})
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.labels.get("llpk1")=="spam" and g2.label_at.get("llpk1"), "the label and its time survive a restart")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
