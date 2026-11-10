# 6.32.0: keeping bots off Public and stopping repeat sends are standard features, on by default, with a switch
# in Settings. All names and messages are made up.
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
D=sg.DEFAULT_CONFIG
check(D["public_bots"] is True and D["public_bots_log_only"] is False and D["quick_resend_hold"] is True,"on by default")
for k in ("public_bots","public_bots_log_only","quick_resend_hold"):
    meta=sg.META_BY_KEY[k]
    check(meta["group"]!="Experimental" and "experimental" not in meta["label"].lower(),f"{k} is a normal setting")
NEW=dict(public_bots=True, public_bots_log_only=False, quick_resend_hold=True)
m=mock(); g=guard(m, floodguard=False, known_min_msgs=1, **NEW); g.apply_settings({"mode":"protect"})
m.add("Bot A","!ping",["4C"],ago=50); cycle(g)
check(m.decide("Bot B","!ping",["4C"])=="drop","a bot command on Public is stopped")
check(m.decide("Bot B","!ping",["4C"],key=sg.hashtag_secret("#test"))=="allow","other channels are never touched")
T="Morning all, is the north repeater working for anyone today?"
m.add("Gus",T,["4C"],ago=40); m.add("Gus",T,["4C"],ago=20); cycle(g)
check(any(k.startswith("resend:") for k in g.blocks),"a quick repeat send is held")
# the owner's own choice wins over the new default
m=mock(); g=guard(m, floodguard=False, public_bots=False, quick_resend_hold=False); g.apply_settings({"mode":"protect"})
check(not g.cfg["public_bots"] and not g.cfg["quick_resend_hold"],"switched off, they stay off")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
