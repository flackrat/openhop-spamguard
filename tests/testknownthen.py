# The evidence log records whether a sender was known when their message ARRIVED (known_then) and
# whether a message was held only for passing THROUGH a blocked repeater (in_passing). All data made up.
import sys, logging, time, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m, evidence_log=True, evidence_dir=os.path.join(TMP,"ev_kt"))
g.apply_settings({"mode":"protect","hop_match_mode":"contains_known"})
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=3000)   # a regular
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Hilltop Hiker"),"regular is known")
g.action("block_hop",{"hop":"98"})
for b in g.blocks.values(): b["created"]-=5000
m.add("Canal Boat Ted","Anyone hearing me from the lock?",["A7","98","2F"],ago=300)   # brand new, passes THROUGH 98
m.add("Hilltop Hiker","Back home now, good signal today",["B1","98","2F"],ago=299)   # regular, passes through 98
m.add(rname(),"FREE PRIZE claim now https://spam.example/x1",["98","2F"],ago=298)    # starts AT 98
g.poll_once(); g.poll_once()
g.log_messages(list(g.events))
rows=[json.loads(l) for l in g.evidence.export(1,False).splitlines() if l.strip()]
msgs={r["sender"]:r for r in rows if r.get("type")=="msg" and r["ts"]>time.time()-400}
ted=msgs.get("Canal Boat Ted"); hik=[r for r in rows if r.get("type")=="msg" and r["sender"]=="Hilltop Hiker" and r["ts"]>time.time()-400]
spam=[r for r in msgs.values() if r["sender"] not in ("Canal Boat Ted","Hilltop Hiker")]
check(ted and ted["caught_by"]=="hop:98","new sender passing through 98 is held: "+str(ted and ted["caught_by"]))
check(ted and ted["known_then"] is False and ted["known"] is True,"known_then False but known after: "+str(ted and (ted["known_then"],ted["known"])))
check(ted and ted["in_passing"] is True,"in_passing recorded")
check(hik and hik[0]["caught_by"] is None and hik[0]["known_then"] is True,"regular through 98 let through and known_then True")
check(spam and spam[0]["in_passing"] is False,"spam starting at 98 is not 'in passing'")
print(f"{ok}/{ok+fail} passed")
