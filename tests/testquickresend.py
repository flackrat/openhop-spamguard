# Accidental double sends: the same name sending the same message again within a couple of minutes is counted
# with its airtime, the first copy is left alone, further copies are held briefly. All names are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
T="Morning all, is the Exmouth repeater working for anyone today?"

m=mock(); g=guard(m, known_min_msgs=1); g.apply_settings({"mode":"protect"})
m.add("Sam Walker",T,["4C","2F"],ago=100); cycle(g)
check(g.stats.get("resends",0)==0,"one send is not a resend")
m.add("Sam Walker",T,["4C","2F"],ago=80); cycle(g)
check(g.stats.get("resends",0)==1,"same name, same text, 20 s later is one resend")
check(g.status()["summary"]["resends_24h"]==1,"shown in the summary")
check(any(k.startswith("resend:") for k in g.blocks),"a short hold is written")
m.add("Sam Walker",T,["4C","2F"],ago=10); cycle(g)
check(g.stats.get("resends",0)==2,"a third copy is counted too")

# other names, short text, slow resends and the switch
m=mock(); g=guard(m, known_min_msgs=1); g.apply_settings({"mode":"protect"})
m.add("Ann",T,["4C"],ago=100); m.add("Bob",T,["4C"],ago=90)
m.add("Ann","Morning",["4C"],ago=80); m.add("Ann","Morning",["4C"],ago=70)
m.add("Cat",T,["4C"],ago=1000); m.add("Cat",T,["4C"],ago=10)
cycle(g)
check(g.stats.get("resends",0)==0,"other names, short text and slow repeats are not resends")
m=mock(); g=guard(m, known_min_msgs=1, quick_resend=False); g.apply_settings({"mode":"protect"})
m.add("Sam",T,["4C"],ago=100); m.add("Sam",T,["4C"],ago=80); cycle(g)
check(g.stats.get("resends",0)==0 and not any(k.startswith("resend:") for k in g.blocks),"switched off: nothing counted or held")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
