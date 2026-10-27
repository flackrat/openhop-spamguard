# Blocking a route from the page: the form in Blocks, and the button on a spam message's details, both reach
# SpamGuard and the block is listed in plain words. Made-up data only.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
import tempfile
ev=tempfile.mkdtemp(prefix="sg-rui-"); now=time.time()
rows=[{"type":"msg","ts":now-600-i*20,"sender":f"RND{i}XQZ7","text":"FREE PRIZE claim now at spam.example/win","path":["9D","4C","2F"],"channel":"Public","caught_by":"text:a","caught_kind":"text","caught_source":"dedupe","random":True} for i in range(3)]
with open(os.path.join(ev,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows))
g.file_cfg["evidence_log"]=True; g.file_cfg["evidence_dir"]=ev; g.rebuild_cfg()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto("http://127.0.0.1:18171/#/messages?f=stopped"); await pg.wait_for_timeout(1800)
        await pg.click("#qList [data-qi='0']"); await pg.wait_for_timeout(400)
        det=await pg.text_content("#qDetail")
        check("Block route 9D>4C" in det, f"a spam message offers to block the route it started on: {det[:300]}")
        await pg.click("#qDetail [data-p='/block_route']"); await pg.wait_for_timeout(1500)
        check("route:9D>4C" in g.blocks, "and blocks it, after asking")
        await pg.goto("http://127.0.0.1:18171/#/blocks"); await pg.wait_for_timeout(1500)
        t=await pg.text_content("body")
        check("started on route 9D>4C" in t, "the route block is listed in plain words")
        await pg.evaluate("document.querySelectorAll('section.adv').forEach(s=>s.style.display='block')")
        await pg.fill("#routeIn","b1>2f"); await pg.click("#routeBtn"); await pg.wait_for_timeout(1500)
        check("route:B1>2F" in g.blocks, "the Route form in Blocks adds one too")
        await pg.fill("#routeIn","b1"); await pg.click("#routeBtn"); await pg.wait_for_timeout(1200)
        t=await pg.text_content("body")
        check("first 2 to 4 repeaters" in t, "a route of one repeater is explained, not added")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
