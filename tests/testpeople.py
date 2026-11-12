# The People list: standing in words, usual way in and last route, on watch that comes off by itself, names that
# age out, and a list that is searched, filtered and paged. All names, messages and repeater codes are made up.
import sys, logging, time, os
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
FAST=dict(floodguard=False,known_min_msgs=3,known_min_minutes=60,vary_limits=False)
m=mock(); g=guard(m,**FAST)
for i in range(10): m.add("Ann Hill",f"{words[i%11]} {words[(i*3)%11]} chat {i}",["4C"] if i%3 else ["5E","4C"],ago=7000-i*600)
m.add("Trail Runner 7","anyone about on the ridge today",["C4","9D"],ago=300)
g.apply_settings({"mode":"protect"}); sync(g)
P=lambda **b: g.people(b)
row=lambda n,**b: next(r for r in g.people(dict(b,show="all",q=n))["rows"] if r["name"]==n)
a=row("Ann Hill")
check(a["standing"]=="known" and "ordinary message" in a["why"],"standing is given in words with the reason: "+a["why"])
check(a["usual"][0]=="4C" and a["last_route"] and not a["unusual"],"usual way in and last route are listed")
t=row("Trail Runner 7")
check(t["standing"]=="learning" and t["usual"]==[] and t["forget_at"],"a new name is learning, with no usual way in yet")
check("score" not in a and all(isinstance(v,(str,bool,int,float,list,dict,type(None))) for v in a.values()),"no invented score")
# heard through a repeater they never use: flagged as possibly a copy
m.add("Ann Hill","hello from far away",["E7","9B","2D"]); sync(g)
check(row("Ann Hill")["unusual"],"a last route that isn't a usual way in is flagged")
m.add("Ann Hill","back home again",["4C"]); sync(g)
check(not row("Ann Hill")["unusual"],"and cleared when they are next heard the usual way")

# On watch: loses the known pass, keeps what it built up, and is listed first
g.action("watch",{"name":"Ann Hill","on":True})
check(not g.is_known("Ann Hill") and g.known["Ann Hill"][2]>=10,"on watch: treated as a stranger, history kept")
r=P(show="active")["rows"]
check(r[0]["name"]=="Ann Hill" and r[0]["standing"]=="watch" and r[0]["watch"]["need"]==g.WATCH_DAYS,"listed first, with the days needed")
check(P()["counts"]["watch"]==1 and g.status()["known"]["watching"]==1,"and counted")
# a spam answer on a known name puts it on watch instead of forgetting it
g.known["Tom Reed"]=[time.time()-7200,time.time()-60,8]; g.homes["Tom Reed"]={"4C":8}
g.action("label",{"label":"spam","sender":"Tom Reed","text":"buy cheap widgets","path":["4C"],"packet":"p1"})
check("Tom Reed" in g.on_watch and "Tom Reed" in g.known and not g.is_known("Tom Reed"),"your spam answer puts a known name on watch")

# It comes off by itself after enough ordinary days and messages
w=g.on_watch["Ann Hill"]; w["since"]=w["clean_from"]=time.time()-8*86400; w["seen"]=0
g.review_watch([],time.time())
check("Ann Hill" in g.on_watch,"quiet alone is not enough: ordinary messages are needed too")
evs=[sg.Event(ts=time.time()-3*86400+i,sender="Ann Hill",text=f"ordinary {i}",path=["4C"],channel="Public") for i in range(3)]
g.review_watch(evs,time.time())
check("Ann Hill" not in g.on_watch and g.is_known("Ann Hill"),"off watch after normal days, and known again at once")
# A message of theirs held for what it did starts the wait again, and makes it longer
g.action("watch",{"name":"Ann Hill","on":True}); w=g.on_watch["Ann Hill"]; w["since"]=w["clean_from"]=time.time()-6*86400
g._add_block("repeat:w","repeat","same line","test","repeat",channel="Public",extra={"who":"Ann Hill"}); w["last_hold"]=0
e=sg.Event(ts=time.time()-60,sender="Ann Hill",text="same line",path=["4C"],channel="Public"); e.matched="repeat:w"
g.review_watch([e],time.time())
check(g.on_watch["Ann Hill"]["need"]==2*g.WATCH_DAYS and g.on_watch["Ann Hill"]["clean_from"]>time.time()-120,"a hold restarts the wait and doubles it")
# ...but not a hold through a repeater they never use (more likely a copy), nor a block meant for strangers
w=g.on_watch["Ann Hill"]; w["last_hold"]=0; before=(w["need"],w["clean_from"])
e2=sg.Event(ts=time.time()-30,sender="Ann Hill",text="same line",path=["E7","9B"],channel="Public"); e2.matched="repeat:w"
g._add_block("hop:C9","hop","C9","test","hop",ttl=600)
e3=sg.Event(ts=time.time()-20,sender="Ann Hill",text="passing by",path=["4C","C9"],channel="Public"); e3.matched="hop:C9"
g.review_watch([e2,e3],time.time())
check((w["need"],w["clean_from"])==before,"a hold elsewhere, or by a block meant for strangers, doesn't count against them")
g.action("watch",{"name":"Ann Hill","on":False})
check("Ann Hill" not in g.on_watch and g.is_known("Ann Hill"),"you can take a name off watch yourself")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check("Tom Reed" in g2.on_watch and g2.last_way.get("Ann Hill"),"remembered after a restart")

# Ageing: a name that never became known is dropped after a week unheard; known people after the usual time
g.known["One Off"]=[time.time()-9*86400,time.time()-8*86400,1]
g.known["Old Regular"]=[time.time()-40*86400,time.time()-20*86400,30]
g.forget_old_names()
check("One Off" not in g.known,"a name heard once and never again is dropped")
check("Old Regular" in g.known and row("Old Regular")["quiet"] and P(show="quiet")["counts"]["quiet"]>=1,"a known person not heard lately is kept, under Not heard lately")
check(not any(r["name"]=="Old Regular" for r in P(show="active")["rows"]),"and is out of the everyday list")
g.known["Old Regular"][1]=time.time()-31*86400; g.forget_old_names()
check("Old Regular" not in g.known,"then forgotten after a month unheard")

# A big list: filtered, searched, sorted and paged by SpamGuard
now=time.time()
for i in range(400): g.known[f"{chr(65+i%26)}name {i:03d}"]=[now-5*86400,now-i*60,12]
for i in range(300): g.known[f"new {i:03d}"]=[now-3600,now-i*30,1]
d=P(show="active")
check(len(d["rows"])==20 and d["total"]>=400 and d["counts"]["learning"]>=300,"one screenful at a time, with counts for each group")
check(not any(r["standing"]=="learning" for r in d["rows"]),"names still being learnt stay out of the everyday list")
d2=P(show="active",offset=20)
check(d2["rows"] and d2["rows"][0]["name"] not in {r["name"] for r in d["rows"]},"the next screenful follows on")
check([r["name"] for r in P(show="all",q="name 01")["rows"]][:1] and all("name 01" in r["name"].lower() for r in P(show="all",q="NAME 01")["rows"]),"search finds names, capitals ignored")
dn=P(show="known",sort="name")
names=[r["name"] for r in dn["rows"]]
check(names==sorted(names,key=str.lower) and dn["letters"] and dn["letters"][0][1]==0,"A to Z, with where each letter starts")
jump=dict((l,o) for l,o in dn["letters"])["M"]
check(P(show="known",sort="name",offset=jump)["rows"][0]["name"].upper().startswith("M"),"jumping to a letter lands on it")
check(P(show="known",sort="msgs")["rows"][0]["msgs"]>=12,"or most messages first")
check(len(P(limit=5000)["rows"])<=100 and P(show="nonsense")["show"]=="active","limits and unknown filters are handled")
check("people" not in g.status()["known"],"the page's regular update no longer carries everyone")
ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check('data-page="exceptions"' not in ui and 'data-page="people"' in ui and 'id="trustHops"' in ui and 'id="suppressed"' in ui,"People replaces Exceptions, and its other lists moved")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
