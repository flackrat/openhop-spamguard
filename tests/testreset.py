import json
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=0; fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock()
for i in range(3): m.add("Hilltop Hiker",f"morning all {i}",["44","13"],ago=600-i*60)
g=guard(m)
g.apply_settings({"mode":"protect","sensitivity":"strict","window_seconds":900})
g.apply_settings({"evidence_log":True,"evidence_days":10}); g.action("allow_sender",{"sender":"Somebody"}); g.action("allow_hop",{"hop":"99"})
for i in range(8): m.add(rname(),"WIN A PRIZE now https://spam.example/"+rname(4),["76","04"])
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
hop=[k for k,b in g.blocks.items() if b["kind"]=="hop"]
check(hop, "hop block created")
g.action("unblock",{"key":hop[0]})
check(hop[0] in g.suppressed, "suppressed after manual remove")
for i in range(4): m.add(rname(),"WIN A PRIZE now https://spam.example/"+rname(4),["76","04"])
g.poll_once()
check(hop[0] not in g.blocks, "not recreated while suppressed")
try:
    g.action("reset_all",{}); check(False,"reset without confirm should fail")
except ValueError: check(bool(g.blocks) or bool(g.suppressed),"nothing cleared without confirm")
r=g.action("reset_all",{"confirm":"RESET"})
check(not g.blocks and not g.suppressed, "blocks and suppressions cleared")
check(not g.allow_senders and not g.allow_hops, "exceptions cleared")
check(g.cfg["mode"]=="protect", "Protect kept"); check(g.cfg["evidence_log"] is True and g.cfg["evidence_days"]==10, "evidence log kept")
check(g.cfg["sensitivity"]=="balanced" or g.cfg["sensitivity"]==sg.DEFAULT_CONFIG.get("sensitivity"), "sensitivity default: "+str(g.cfg["sensitivity"]))
check(g.cfg["window_seconds"]==sg.PRESETS[g.cfg["sensitivity"]].get("window_seconds",sg.DEFAULT_CONFIG["window_seconds"]) , "window default")
check("Hilltop Hiker" in g.known, "regular relearnt as known")
st=g.status()
check(not st["recent"], "messages list starts empty after reset")
check(len(st["activity"])==1 and "from scratch" in st["activity"][0]["msg"], "activity starts at the reset: "+str(st["activity"][:2]))
check(st["summary"]["caught_24h"]==0, "charts start again from the reset")
if g.evidence:
    out=g.evidence.export(30, False)
    check(any(json.loads(l)["ts"]<g.reset_at for l in out.splitlines() if l.strip()), "evidence log still has everything from before the reset")
check(len(g.activity)>1, "earlier activity is kept, only hidden on the page")
for i in range(8): m.add(rname(),"WIN A PRIZE again https://spam.example/"+rname(4),["76","04"])
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(any(b["kind"]=="hop" for b in g.blocks.values()), "hop block recreated straight after reset")
rules=[r for r in m.policy["policy_engine"]["rules"] if str(r.get("name","")).startswith("spamguard:")] if hasattr(m,"policy") else None
print("rules in openHop:", None if rules is None else len(rules))
g.apply_settings({"reset":True}); check(g.cfg["evidence_log"] is True, "settings reset keeps evidence log")
print(f"{ok}/{ok+fail} passed"); print(r)
