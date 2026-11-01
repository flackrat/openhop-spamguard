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

m=mock(); g=guard(m, known_min_msgs=1, quick_resend_hold=True); g.apply_settings({"mode":"protect"})
m.add("Sam Walker",T,["4C","2F"],ago=60); cycle(g)
check(g.stats.get("resends",0)==0,"one send is not a resend")
m.add("Sam Walker",T,["4C","2F"],ago=40); cycle(g)
check(g.stats.get("resends",0)==1,"same name, same text, 20 s later is one resend")
check(g.status()["summary"]["resends_24h"]==1,"shown in the summary")
check(any(k.startswith("resend:") for k in g.blocks),"a short hold is written")
m.add("Sam Walker",T,["4C","2F"],ago=15); cycle(g)
check(g.stats.get("resends",0)==2,"a third copy is counted too")

# other names, short text, slow resends and the switch
m=mock(); g=guard(m, known_min_msgs=1, quick_resend_hold=True); g.apply_settings({"mode":"protect"})
m.add("Ann",T,["4C"],ago=100); m.add("Bob",T,["4C"],ago=90)
m.add("Cat",T,["4C"],ago=1000); m.add("Cat",T,["4C"],ago=10)
cycle(g)
check(g.stats.get("resends",0)==0,"other names and slow repeats are not resends")
m=mock(); g=guard(m, known_min_msgs=1, quick_resend=False); g.apply_settings({"mode":"protect"})
m.add("Sam",T,["4C"],ago=100); m.add("Sam",T,["4C"],ago=80); cycle(g)
check(g.stats.get("resends",0)==0 and not any(k.startswith("resend:") for k in g.blocks),"switched off: nothing counted or held")
m=mock(); g=guard(m, known_min_msgs=1, quick_resend_hold=True); g.apply_settings({"mode":"protect"})
m.add("Ann","Hello",["4C"],ago=50); m.add("Ann","Hello",["4F","2A"],ago=30); cycle(g)
check(g.stats.get("resends",0)==1,"short messages count too, from the same sender on any path")
check(not any(k.startswith("resend:") for k in g.blocks),"but a word or two is never held")
m=mock(); g=guard(m, known_min_msgs=1, quick_resend_hold=True); g.apply_settings({"mode":"protect"})
m.add("Dan",T,["4C"],ago=100); m.add("Dan",T,["4C"],ago=40); cycle(g)
check(g.stats.get("resends",0)==0,"60 s apart is too slow to count")
# The first copy must have been passed on; an echo through another repeater confirms it
def pkt(m,sender,text,path,ago,h,**extra):
    m.add(sender,text,path,ago=ago); m.packets[-1]["packet_hash"]=h; m.packets[-1].update(extra)
m=mock(); g=guard(m, quick_resend_hold=True); g.apply_settings({"mode":"protect"}); g.me={"name":"me","hash":"A1"}
pkt(m,"Eve",T,["4C"],40,"aa"*8,transmitted=False)
pkt(m,"Eve",T,["4C"],20,"bb"*8,transmitted=True); cycle(g)
check(g.stats.get("resends",0)==0 and g.stats.get("retries",0)==1,"first copy never passed on: a retry, not a resend")
check(not any(k.startswith("resend:") for k in g.blocks),"and nothing is held")
check(g.status()["summary"]["retries_24h"]==1,"retries shown in the summary")
m=mock(); g=guard(m, quick_resend_hold=True); g.apply_settings({"mode":"protect"}); g.me={"name":"me","hash":"A1"}
pkt(m,"Fay",T,["4C"],40,"cc"*8,transmitted=True)
pkt(m,"Fay",T,["4C"],20,"dd"*8,transmitted=True); cycle(g)
check(g.stats.get("resends",0)==1 and any(k.startswith("resend:") for k in g.blocks),"first copy passed on: a resend, held")
check(g.status()["summary"]["resends_confirmed_24h"]==0,"no echo heard: not confirmed")
g.me={"name":"me","hash":"A1"}
pkt(m,"Fay",T,["4C","A1","7E"],39,"cc"*8); cycle(g)
check(g.status()["summary"]["resends_confirmed_24h"]==1,"first copy heard coming back through another repeater: confirmed")
check(g.status()["summary"]["resend_echoes_24h"]==1,"one repeater took it from us")
pkt(m,"Fay",T,["4C","A1","7E"],38,"cc"*8); pkt(m,"Fay",T,["4C","A1","9B"],37,"cc"*8); cycle(g)
check(g.status()["summary"]["resend_echoes_24h"]==2,"the same repeater twice counts once, a different one counts again")
# The hold is an experimental opt-in: by default it counts and holds nothing
m=mock(); g=guard(m, known_min_msgs=1); g.apply_settings({"mode":"protect"})
m.add("Gus",T,["4C"],ago=40); m.add("Gus",T,["4C"],ago=20); cycle(g)
check(g.stats.get("resends",0)==1 and not any(k.startswith("resend:") for k in g.blocks),"default: counted, never held")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
