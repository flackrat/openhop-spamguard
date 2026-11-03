# Several messages can be ticked and labelled together: on the Messages screen (tick all, shift-click a range)
# and in the Overview's "worth a look" list. All names and messages are made up.
import sys, os, time, asyncio, json, tempfile
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
ev=tempfile.mkdtemp(prefix="sg-ml-"); now=time.time()
rows=[{"type":"msg","ts":now-900+i,"sender":f"Loud Larry {i}","text":f"Visit my totally great page number {i} today everyone","path":["C4","2F"],"channel":"Public","packet":f"mlpk{i}"} for i in range(5)]
with open(os.path.join(ev,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows))
g.file_cfg["evidence_log"]=True; g.file_cfg["evidence_dir"]=ev; g.rebuild_cfg()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            pg=await (await b.new_context(viewport={"width":1280,"height":900},color_scheme=scheme)).new_page()
            errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
            sent=[]
            async def route(r):
                sent.append(json.loads(r.request.post_data or "{}")); await r.fulfill(status=200,content_type="application/json",body="{}")
            await pg.route("**/label",route)
            await pg.goto("http://127.0.0.1:18171/#/messages?f=all"); await pg.wait_for_timeout(1800)
            await pg.set_viewport_size({"width":1280,"height":900})
            bar=await pg.text_content("#qBulk")
            check("Select all" in bar and "shift-click" in bar, f"{scheme}: the bar offers select all and says about shift-click")
            await pg.click("#qList [data-qt='0']"); await pg.click("#qList [data-qt='3']",modifiers=["Shift"]); await pg.wait_for_timeout(200)
            n=await pg.eval_on_selector_all("#qList [data-qt]:checked","x=>x.length")
            check(n==4, f"{scheme}: shift-click ticks the range (got {n})")
            check("4 selected" in await pg.text_content("#qBulk"), f"{scheme}: the bar counts them")
            await pg.click("[data-qall]"); await pg.wait_for_timeout(200)   # 4 of 5 ticked -> ticks the rest
            n=await pg.eval_on_selector_all("#qList [data-qt]:checked","x=>x.length")
            check(n==5, f"{scheme}: select all ticks all five (got {n})")
            await pg.click("[data-qall]"); await pg.wait_for_timeout(200)   # all ticked -> unticks everything
            n=await pg.eval_on_selector_all("#qList [data-qt]:checked","x=>x.length")
            check(n==0, f"{scheme}: the select-all box unticks everything when all were ticked (got {n})")
            await pg.click("[data-qall]"); await pg.wait_for_timeout(200)
            await pg.click("[data-qb='spam']"); await pg.wait_for_timeout(600)
            check(len(sent)==5 and all(s.get("label")=="spam" for s in sent), f"{scheme}: five labels sent together (got {len(sent)})")
            # the Overview list, built the way the page builds it
            sent.clear()
            await pg.goto("http://127.0.0.1:18171/#/"); await pg.wait_for_timeout(1200)
            await pg.evaluate("""()=>{ const d=document.createElement('div'); d.id='tmp';
              const items=[1,2,3].map(i=>({packet:'p'+i,sender:'S'+i,text:'t'+i}));
              d.innerHTML='<div class="q-bulk" id="lkBulk">'+lkBarHtml(0,3)+'</div><ul id="lkList">'+items.map(m=>'<li><input type="checkbox" data-lk="'+lkKey(m)+'"><button data-p="/label" data-b=\\''+JSON.stringify({label:"none",sender:m.sender,text:m.text,packet:m.packet})+'\\'>Spam</button></li>').join('')+'</ul>';
              document.body.appendChild(d); }""")
            await pg.click("#lkAll"); await pg.wait_for_timeout(200)
            check("3 ticked" in await pg.text_content("#lkBulk"), f"{scheme}: tick all ticks the three")
            await pg.click("[data-lb='not_spam']"); await pg.wait_for_timeout(600)
            check(len(sent)==3 and all(s.get("label")=="not_spam" for s in sent), f"{scheme}: three fine labels sent (got {len(sent)})")
            check(not errs, f"{scheme}: no page errors "+str(errs))
        await b.close()
asyncio.run(main())
print("testmultilabelui: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
