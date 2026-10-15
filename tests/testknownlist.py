# Known people can be seen and edited: the list shows who SpamGuard has learnt, Trust keeps a name for good,
# Forget makes them count as new again (and takes them out of the list openHop lets through).
# All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all from the hill","Nice and clear today"]):
    m.add("Quarry Pete",t,["4C","2F"],ago=600-i*60)
m.add("Canal Boat Ted","Anyone hearing me from the lock?",["B1","2F"],ago=300)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
ppl={p["name"]:p for p in g.status()["known"]["people"]}
check(ppl.get("Quarry Pete",{}).get("known") and ppl["Quarry Pete"]["msgs"]==2,"known person listed with message count: "+str(ppl.get("Quarry Pete")))
check(ppl.get("Canal Boat Ted",{}).get("known") is False,"one message: still being learnt")
check("text" not in json.dumps(g.status()["known"]),"no message text in the list")
g.action("allow_sender",{"sender":"Canal Boat Ted"})
ppl={p["name"]:p for p in g.status()["known"]["people"]}
check(ppl["Canal Boat Ted"]["trusted"],"Trust marks a name trusted")
g.action("block_hop",{"hop":"4C"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(m.decide("Quarry Pete","Back again",["4C","2F"])=="allow","known person gets through a repeater block")
g.action("forget_known",{"name":"Quarry Pete"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.is_known("Quarry Pete"),"forgotten")
check(m.decide("Quarry Pete","Back again",["4C","2F"])=="drop","after Forget they are new again, so the block applies")
try: g.action("forget_known",{"name":"Nobody"}); check(False,"unknown name refused")
except ValueError: check(True,"")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
