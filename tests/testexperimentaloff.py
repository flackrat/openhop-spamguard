# With every experimental feature off (the default), nothing experimental happens: no rules, no holds, no
# learning, and the same blocks as with the features left out. All names and messages are made up.
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
ACK="@[Sam], ack: SNR 12.0 dB, RSSI -52 dBm, 9 hops via 4E, B7, 9C"
T="Morning all, is the Exmouth repeater working for anyone today?"
SPAM="Win a free prize now, visit freeprizes.example today and claim it before midnight"
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
check(not any(sg.DEFAULT_CONFIG[k] for k in ("text_sense","spoof_watch","show_experimental")),"every experimental switch is off by default")
check(all(m_["group"]!="Experimental" for m_ in sg.SETTINGS_META if m_["key"] in ("public_bots","quick_resend_hold")),"bots and repeat sends are no longer experimental")
for i in range(8): m.add(f"Regular {i}","Lovely morning on the hill, clear skies and good signal",["4C","2F"],ago=90000-i*9000)
m.add("Bot A",ACK,["4C"],ago=300); m.add("Bot B","!ping",["4C"],ago=290)
m.add("Sam",T,["4C"],ago=60); m.add("Sam",T,["4C"],ago=40); m.add("Sam",T,["4C"],ago=20)
for i in range(6): m.add(f"Pedlar {i}x{i}9",SPAM,["4C","2F"],ago=200-i*10)
cycle(g)
names=[r["name"] for r in m.policy["policy_engine"]["rules"]]
check(not any("bots on Public" in n for n in names),"no bot rules")
check(not any(k.startswith("resend:") for k in g.blocks),"no double-send holds")
check(g.sense.n[0]==0 and g.sense.n[1]==0,"nothing learnt")
check(g.stats.get("pubbots",0)==0,"bots on Public are not even counted")
check(g.stats.get("resends",0)>=1,"double sends are counted (that part is on by default)")
check(any(b.get("source")=="dedupe" or b["kind"] in ("text","words") for b in g.blocks.values()),"ordinary spam defences still work")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
