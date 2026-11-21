# Rule writes are batched: a new hold or a tighter flood limit goes to openHop at once; tidying up (people
# becoming known, holds ending, marking messages) waits and goes together. Made-up data.
import sys, logging, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m)
g.poll_once()
p0=m.posts
check(p0>=1,"first sync writes the rules")
# tidying only: waits for the batch (a hold ending)
g._add_block("text:gone","text","limited offer click now friends","made up","campaign",channel="Public")
g.sync_pending=True; g.last_sync-=3; g.poll_once(); p0=m.posts
g.blocks.pop("text:gone"); g.sync_pending=True; g.last_sync-=3; g.poll_once()
check(m.posts==p0,"a change that only tidies waits for the batch")
check(g.sync_pending,"...and is still waiting, not lost")
g.last_sync-=g.SYNC_BATCH_SECONDS+1; g.poll_once()
check(m.posts==p0+1,"...and goes out once the batch time has passed")
# a new hold: at once
p1=m.posts
g._add_block("text:test1","text","buy cheap pills here today","made up","campaign",channel="Public")
g.sync_pending=True; g.last_sync-=3; g.poll_once()
check(m.posts==p1+1,"a new hold is written at once")
check(any("text:test1" in str(r.get("name")) for r in m.policy["policy_engine"]["rules"]),"...and is in openHop")
check(m.decide("Stranger 7","buy cheap pills here today please",["A1","B2"])=="drop","...and openHop stops it straight away")
# a page action that only marks: no forced write
p2=m.posts
g.last_sync-=3
g.action("hide_source",{"hop":"AB"})
g.poll_once()
check(m.posts==p2,"marking or dismissing on the page waits for the batch")
# a settings change on the page: at once
g.apply_settings({"mode":"monitor"}); g.poll_once()
check(m.posts==p2+1,"a settings change is written at once")
# a tighter flood limit: at once
g.apply_settings({"mode":"protect"}); g.poll_once(); p3=m.posts
g._urgent_sync=True; g.sync_pending=True; g.last_sync-=3; g.poll_once()
check(m.posts==p3+1,"a flood limit change marked urgent is written at once")
# the urgent flag is cleared after a write
check(not getattr(g,"_urgent_sync",False),"urgent flag cleared after writing")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
