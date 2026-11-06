# 6.27.4: a route that was blocked in the last few days comes back after fewer made-up names. All names are made up.
import sys, logging, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
TXT="Cheap watches and free prizes waiting for you on my page tonight"
NOISE=("P/M£<$£H","8KN_<%RV","I)*D6R<$",">8=2-A__","S</D_*_P","_HX4L<_:","Q,ZWX*%B")
tails=(["04","F0","91","AD"],["04","F0","36","AD","79"],["04","F0","9C","76"],["04","F0","36","C2","09"],["04","F0","91","DB"],["04","F0","B1","91"])
def stems(g): return [k for k,b in g.blocks.items() if b["kind"]=="stem"]
def two_names(m, first="07"):
    for i,n in enumerate(NOISE[:2]): m.add(n,"%s %d"%(TXT,i),[first]+tails[i],ago=200-i*20)

# 1. Without any memory, two names do nothing
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"}); two_names(m); cycle(g)
check(not stems(g),"two made-up names alone start nothing")

# 2. With a stem blocked an hour ago, two new names start it again
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
two_names(m); cycle(g)
check(stems(g)==["stem:04>F0"],"a route blocked an hour ago comes back after two names (got %s)"%stems(g))
check(g.blocks["stem:04>F0"]["source"]=="rotation","it is a rotation-style block")
check(m.decide("Z9QQ<K/A","Lovely views today, anyone out?",["DD","04","F0","91"])=="drop","a new name behind another first repeater is dropped")

# 3. Memory older than a week is ignored
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-9*86400
two_names(m); cycle(g)
check(not stems(g),"a route blocked nine days ago needs the full number of names again")

# 4. A different route is not helped by another route's memory
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["59>77"]=time.time()-3600
two_names(m); cycle(g)
check(not stems(g),"memory of one route does not help another")

# 5. Known people still pass, and three regulars on the route cancel it
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
m.add("Andy Example","Morning all",["73","8D"],ago=900); m.add("Andy Example","Anyone about?",["73","8D"],ago=800)
two_names(m); cycle(g); cycle(g)
check(m.decide("Andy Example","Anyone on the hill this morning?",["07","04","F0","91"])!="drop","a known person on the route passes")
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
now=time.time()
for r in ("Reg One","Reg Two","Reg Three"):
    g.sender_history[r]={"first":now-5*3600,"count":30,"last":now-300,"hops":set()}
    m.add(r,"Evening all, anyone on the air?",["59","04","F0"],ago=100)
two_names(m); cycle(g)
check(not stems(g),"three regulars behind the route: memory does not rebuild it")

# 6. Ordinary-looking names never count, even with memory
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
for i,n in enumerate(("Hilltop Hiker","Brook Walker")): m.add(n,"Morning all number %d, anyone about?"%i,["07"]+tails[i],ago=200-i*20)
cycle(g)
check(not stems(g),"two ordinary names never rebuild a route")

# 7. Making a stem block writes it to memory; memory survives a restart; a reset clears it
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i,n in enumerate(NOISE[:6]): m.add(n,"%s %d"%(TXT,i),["07"]+tails[i],ago=200-i*20)
cycle(g)
check(stems(g)==["stem:04>F0"] and "04>F0" in g.stem_memory,"a new stem block is remembered")
g._save_state(force=True)
st=os.path.join(TMP, f"state_{PORT[0]}.json")
g2=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}","api_key":"t","mode":"protect","state_file":st,
                 "known_min_msgs":1,"known_min_minutes":0,"vary_limits":False})
check("04>F0" in g2.stem_memory,"memory survives a restart")
g2.reset_all()
check(not g2.stem_memory,"a reset clears it")

# 8. Old entries are dropped when loading
m=mock(); g=guard(m, floodguard=False); g.stem_memory["04>F0"]=time.time()-10*86400; g.stem_memory["59>77"]=time.time()-60
g._save_state(force=True)
st=os.path.join(TMP, f"state_{PORT[0]}.json")
g3=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}","api_key":"t","mode":"protect","state_file":st,
                 "known_min_msgs":1,"known_min_minutes":0,"vary_limits":False})
check(list(g3.stem_memory)==["59>77"],"entries older than a week are not loaded")

# 9. 6.27.5: a suppressed (hand-removed) block does not refresh memory
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
old=time.time()-3*86400
g.stem_memory["04>F0"]=old
g.suppressed["stem:04>F0"]=time.time()+3600
two_names(m); cycle(g)
check(not stems(g),"a suppressed route is not rebuilt")
check(g.stem_memory.get("04>F0")==old,"a block that was not made does not refresh memory")

# 10. Removing a stem block by hand forgets the route
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
two_names(m); cycle(g)
check(stems(g)==["stem:04>F0"],"rebuilt with memory")
g.blocks.pop("stem:04>F0"); g.stem_memory.pop("04>F0",None)
two_names(m); cycle(g)
check(not stems(g),"after hand removal, two names are not enough")

# 11. Two unrelated newcomers with ordinary names on a remembered route are not held
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
g.stem_memory["04>F0"]=time.time()-3600
for i,n in enumerate(("Pat Walker","Sam Baker")): m.add(n,"Hello from the valley, first time on here %d"%i,["07"]+tails[i],ago=200-i*20)
cycle(g)
check(not stems(g) and m.decide("Pat Walker","Hello again",["07","04","F0","91"])!="drop","new ordinary users on a remembered route are not held")

# 12. Malformed or hand-edited state loads safely
import json
m=mock(); g=guard(m, floodguard=False)
g._save_state(force=True)
st=os.path.join(TMP, f"state_{PORT[0]}.json")
d=json.load(open(st)); n=time.time()
d["stem_memory"]={"04>F0":"x","59>77":-5,"AA>BB":float("nan"),"CC>DD":1e300,"EE>FF":True,"nonsense":n,"04>":n,"11>22":n+10*86400,"A"*500:n,"33>44":n-60}
json.dump(d,open(st,"w"))
g4=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}","api_key":"t","mode":"protect","state_file":st,
                 "known_min_msgs":1,"known_min_minutes":0,"vary_limits":False})
check(list(g4.stem_memory)==["33>44"],"only well-formed, recent entries load (got %s)"%list(g4.stem_memory))
for bad in ("text",[1,2],5,None):
    d["stem_memory"]=bad; json.dump(d,open(st,"w"))
    g5=sg.SpamGuard({"openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}","api_key":"t","mode":"protect","state_file":st,
                     "known_min_msgs":1,"known_min_minutes":0,"vary_limits":False})
    check(g5.stem_memory=={},"wrong type %r loads as empty"%(bad,))

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
