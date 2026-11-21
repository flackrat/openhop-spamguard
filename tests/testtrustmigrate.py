# Upgrading to 6.44: names trusted from the page before (one "Not spam" tap trusted a name everywhere) wait on the
# Overview to be confirmed; names trusted in the config file are kept; a fresh install or a second start moves nothing.
# Checked in the browser too. All names are made up.
import sys, os, time, asyncio, json
exec(open("demo_setup.py").read().replace("18171","18197"))
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
st=os.path.join(TMP,"state_migrate.json")
old={"allow_senders":["Persona Dept","Club Bot","Config Friend"],"known_senders":{"Club Bot":[time.time()-9*86400,time.time()-300,40]}}
json.dump(old,open(st,"w"))
m2=mock()
g2=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m2.srv.server_address[1]}","api_key":"t","state_file":st,
                 "allow_senders":["Config Friend"],"floodguard":False})
check(g2.allow_senders=={"Config Friend"},f"page-trusted names moved out, config-file name kept: {g2.allow_senders}")
check(set(g2.trust_review)=={"Persona Dept","Club Bot"},"both wait for confirmation")
check(any("Trust works differently" in a["msg"] for a in g2.activity),"a note explains it")
rows={r["name"]:r for r in g2._trust_review_rows()}
check(rows["Club Bot"]["known"] and rows["Club Bot"]["msgs"]==40 and not rows["Persona Dept"]["known"],"the list says who SpamGuard knows")
g2._save_state(force=True)
g3=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m2.srv.server_address[1]}","api_key":"t","state_file":st,"floodguard":False})
check(set(g3.trust_review)=={"Persona Dept","Club Bot"} and sum("Trust works differently" in a["msg"] for a in g3.activity)==1,"a second start moves nothing more and doesn't repeat the note")
g3.action("trust_review",{"name":"Club Bot","keep":True})
check("Club Bot" in g3.allow_senders and "Club Bot" not in g3.trust_review,"Trust again: trusted everywhere")
g3.action("trust_review",{"name":"Persona Dept","keep":False})
check("Persona Dept" not in g3.allow_senders and not g3.trust_review,"Don't trust: dropped")
# a fresh install with nothing trusted: nothing to review
st2=os.path.join(TMP,"state_fresh.json")
g4=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m2.srv.server_address[1]}","api_key":"t","state_file":st2,"floodguard":False})
check(not g4.trust_review,"fresh install: nothing to review")
# the browser: the demo guard gets two names to review
g.trust_review={"Persona Dept":time.time(),"Club Bot":time.time()}; g.mark_counts["Persona Dept"]=[3,1,time.time()]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":412,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e))); pg.on("dialog",lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto("http://127.0.0.1:18197/#/"); await pg.wait_for_timeout(1800)
        check(await pg.is_visible("#trustRevSec"),"the Overview shows the check")
        txt=await pg.text_content("#trustRevSec")
        check("Persona Dept" in txt and "marked 3 of their messages as spam" in txt and "one press of" in txt,"with why, and what you'd want to know")
        box=await pg.locator("#trustRevSec").bounding_box()
        check(box["width"]<=412,"fits a phone screen")
        await pg.click("#trustRevList li:has-text('Club Bot') button:has-text('Trust again')"); await pg.wait_for_timeout(1500)
        check("Club Bot" in g.allow_senders,"Trust again works from the page")
        await pg.click("#trustRevAll"); await pg.wait_for_timeout(1800)
        check(not g.trust_review and not await pg.is_visible("#trustRevSec"),"dropping the rest clears the list and the notice goes")
        check(not errs,f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
