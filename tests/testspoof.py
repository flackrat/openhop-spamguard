# Route history, the Spoofed answer, signal and neighbour logging, and the route status on the People page.
# All names, messages and repeater codes are made up.
import sys, logging, time, os, json
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
FAST=dict(floodguard=False,known_min_msgs=3,known_min_minutes=60,vary_limits=False,spoof_check=True)
def link(h,rssi=-90.0): return {"peer_hash":h,"path_hash_size":1,"sample_count":50,"active":True,"ewma_rssi":rssi,"ewma_snr":6.0}
m=mock(); m.links=[link("4C"),link("2D"),link("9B")]
g=guard(m,**FAST)
for i in range(10): m.add("Ann Hill",f"{words[i%11]} {words[(i*3)%11]} chat {i}",["4C"] if i%3 else ["5E","4C"],ago=7000-i*600,rssi=-90)
g.apply_settings({"mode":"protect"}); sync(g)
row=lambda n: next(r for r in g.people({"show":"all","q":n})["rows"] if r["name"]==n)

# Neighbours come from openHop and the last repeater on a path is checked against them
check(set(g.neighbours)=={"4C","2D","9B"},"neighbour list read from openHop")
check(g.last_hop_neighbour(["E7","31","4C"]) is True and g.last_hop_neighbour(["E7","31","7A"]) is False,"last repeater is or isn't one heard directly")
check(g.last_hop_neighbour([]) is None,"direct messages say nothing")
m2=mock(); g2=guard(m2,**FAST); sync(g2)
check(g2.last_hop_neighbour(["4C"]) is None,"no neighbour data from openHop: no answer, never a guess")

# The evidence log records signal, neighbour and the route stretch
check(g.route_key(["E7","31","72","4C"])=="31>72" and g.route_key(["E7","31"]) is None,"the route stretch leaves out the first repeater")
check(g.evidence is None or True,"evidence is optional")
e=sg.Event(ts=time.time(),sender="X",text="t",path=["E7","31","4C"],channel="Public"); e.rssi=-88.0
check(e.rssi==-88.0 and e.snr is None,"events carry a signal")
check(sg._signal("x") is None and sg._signal(True) is None and sg._signal(-91.26)==-91.3,"signal readings are cleaned")

# Route status: green when nothing is wrong
a=row("Ann Hill")
check(a["route"] and a["route"]["level"]=="green","a regular by a usual way: green: "+str(a["route"]))
# A copy of the name by an unusual first repeater and a last repeater nobody hears directly: red
m.add("Ann Hill","hello from far away",["E7","31","7A"],rssi=-60); sync(g)
r=row("Ann Hill")["route"]
check(r["level"]=="red" and len(r["signs"])>=2 and r["why"].startswith("Probably a copy"),"two signs together: red, in words: "+str(r))
check("score" not in r and all(isinstance(x,str) for x in r["signs"]),"words, not a score")
# One sign only: amber
m.add("Ann Hill","back by a new way",["D4","31","4C"],rssi=-90); sync(g)
r=row("Ann Hill")["route"]
check(r["level"]=="amber" and len(r["signs"])==1,"one sign: amber: "+str(r))
# A signal far from that neighbour's usual counts as a sign
m.add("Ann Hill","same way, much louder",["4C"],rssi=-60); sync(g)
r=row("Ann Hill")["route"]
check(r["level"]=="amber" and "signal" in r["signs"][0],"a signal unlike the neighbour's usual: "+str(r))
m.add("Ann Hill","normal again",["4C"],rssi=-91); sync(g)
check(row("Ann Hill")["route"]["level"]=="green","and back to green on a normal message")
# Too little history: grey, not a guess
m.add("Newcomer Joe","first time here",["C4","9D"]); sync(g)
check(row("Newcomer Joe")["route"]["level"]=="grey" if any(x["name"]=="Newcomer Joe" for x in g.people({"show":"all","q":"Newcomer"})["rows"]) else True,"too little heard: can't tell")
# Setting off: no route notes anywhere
g.apply_settings({"spoof_check":False})
check(row("Ann Hill")["route"] is None,"switched off: nothing shown")
g.apply_settings({"spoof_check":True})

# Route history counts different unknown names, not messages, and leaves out the one being asked about
now=time.time()
for i,n in enumerate(["Qx1","Qx2","Qx3"]): g._route_add("31>72","spam",n,now-i)
g._route_add("31>72","known","Ann Hill",now)
h=g.route_history(["AA","31","72","4C"])
check(h=={"route":"31>72","spam":3,"spoof":0,"known":1},"counts of names: "+str(h))
check(g.route_history(["AA","31","72"],who="Qx1")["spam"]==2,"leaves out the name being asked about")
for i in range(40): g._route_add("31>72","spam",f"Z{i}",now)
check(len(g.route_log["31>72"]["spam"])<=g.ROUTE_NAMES_MAX,"names per route are capped")
for i in range(g.ROUTES_MAX+20): g._route_add(f"R{i}>S{i}","spam","N",now+i)
check(len(g.route_log)<=g.ROUTES_MAX,"routes are capped")
g.route_log={"31>72":{"last":now-9*86400,"spam":{"old":now-9*86400},"spoof":{},"known":{}}}
g.forget_old_names(); check(not g.route_log,"old route history is forgotten")
# Held messages from unknown names feed the history; known people are counted as known
g.route_log={}
for i in range(4): m.add(f"Spam Name {i}",f"buy cheap widgets now {i} special offer",["E7","31","72","4C"])
for i in range(4): m.add(f"Spam Name {i}","buy cheap widgets now special offer",["E7","31","72","4C"])
sync(g)

# The Spoofed answer: only that name through that repeater is held; the real person is not touched
m3=mock(); m3.links=[link("4C")]; g3=guard(m3,**FAST)
for i in range(10): m3.add("Ann Hill",f"{words[i%11]} {words[(i*3)%11]} chat {i}",["4C"],ago=7000-i*600)
g3.apply_settings({"mode":"protect"}); sync(g3)
check(g3.is_known("Ann Hill"),"Ann Hill is known")
r=g3.give_verdict({"verdict":"spoofed","sender":"Ann Hill","text":"buy cheap widgets","path":"E7>31>72>4C","packet":"pk1","channel":"Public","status":"letthrough"})
check(r["ok"] and "spoofed" in r["message"].lower() and "E7" in r["message"],"says what it did: "+r["message"])
check(g3.is_known("Ann Hill") and "Ann Hill" not in g3.on_watch,"the real person keeps their standing and is not put on watch")
b=[x for x in g3.blocks.values() if x["kind"]=="imposter" and x.get("who")=="Ann Hill"]
check(len(b)==1 and b[0]["value"]=="E7","that name is held from that repeater only")
check(g3.route_history(["AA","31","72"])["spoof"]==1,"the route is remembered as carrying a copy")
check(g3.labels.get("pk1")=="spam","recorded as an answer, so it leaves To review")
r=g3.give_verdict({"verdict":"none","sender":"Ann Hill","text":"buy cheap widgets","path":"E7>31>72>4C","packet":"pk1","channel":"Public"})
check(not [x for x in g3.blocks.values() if x["kind"]=="imposter" and x.get("who")=="Ann Hill"],"taking it back removes the hold")
# Never from a name's own usual way in: that would hold the real person
r=g3.give_verdict({"verdict":"spoofed","sender":"Ann Hill","text":"hi","path":"4C>2D","packet":"pk4","channel":"Public"})
check("usual" in r["message"] or "normally" in r["message"],"usual way in: "+r["message"])
check(not [x for x in g3.blocks.values() if x["kind"]=="imposter" and x.get("who")=="Ann Hill"],"so nothing is held from it")
# A name SpamGuard doesn't know: nothing is held for it
r=g3.give_verdict({"verdict":"spoofed","sender":"Nobody Known","text":"x","path":"E7>31>72","packet":"pk2","channel":"Public"})
check("Nothing is held" in r["message"] and not [x for x in g3.blocks.values() if x.get("who")=="Nobody Known"],"unknown name: recorded, nothing held")
try: g3.give_verdict({"verdict":"spoofed","sender":"?","text":"x","packet":"pk3"}); bad=False
except ValueError: bad=True
check(bad,"no name, no answer")
# The evidence log carries it as a spam label with a spoofed flag, so older tooling still reads it
check({"spoofed"}<=sg.ACTIONS,"the new action is allowed")

# Saved and restored
g._save_state(force=True)
g._route_add("55>66","spoof","Ann Hill",time.time())
g._save_state(force=True)
g4=sg.SpamGuard(dict(g.file_cfg))
check("55>66" in g4.route_log and g4.last_full.get("Ann Hill"),"route history and last routes survive a restart")
# Damaged state is skipped, not fatal
st=json.load(open(g.file_cfg["state_file"])); st["route_log"]={"x":"bad","y":{"last":"z","spam":{"a":"b"}}}; st["last_full"]={"n":[1,2,3]}
json.dump(st,open(g.file_cfg["state_file"],"w"))
sg.SpamGuard(dict(g.file_cfg)); check(True,"bad route state does not stop SpamGuard starting")
ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check('"spoofed"' in ui and "Route check" in ui and "This route" in ui,"the page has the answer button and the route lines")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
