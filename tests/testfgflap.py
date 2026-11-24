# FloodGuard on/off stability: a radio hovering around the busy level, or bursting on and off, doesn't make the
# flood limit start and lift over and over. It starts once, lifts only after a calm spell well below the level, and
# Activity says when it started, tightened and lifted. Scripted readings, no real radio.
import sys, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
RADIO={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
def setup():
    g=guard(mock(), floodguard=True); g.radio=dict(RADIO); g.refresh_openhop_info=lambda *a,**k: None
    g.fg.update(ready=time.time()-86400, learnt_at=time.time()); g.fg_learn=lambda now: False
    g.cfg["flood_busy_percent"]=20; g.cfg["flood_calm_minutes"]=10
    return g
def run(g, readings, t0, step=10):
    events=[]; t=t0
    for busy in readings:
        g.fg_load=lambda now,b=busy:(b,0.9,200)
        g.fg_decide(t); events.append(g.fg.get("limit")); t+=step
    return events, t
level=20
# 1. hovering: 21, 19, 21, 19 ... every 10 s for 40 minutes
g=setup(); t0=time.time()
lim,_=run(g,[21 if i%2==0 else 19 for i in range(240)],t0)
starts=sum(1 for a,b in zip([None]+lim,lim) if not a and b)
check(starts<=1,"hovering at the level starts it at most once: %d starts"%starts)
# 2. bursts: 90 s busy, 60 s quiet, over and over
g=setup(); t0=time.time()
pat=([35]*9+[5]*6)*16
lim,t=run(g,pat,t0)
starts=sum(1 for a,b in zip([None]+lim,lim) if not a and b); lifts=sum(1 for a,b in zip([None]+lim,lim) if a and not b)
check(starts==1 and lifts==0,"bursts with short gaps keep one episode going: %d starts, %d lifts"%(starts,lifts))
# then a real calm spell lifts it, once
lim2,_=run(g,[5]*80,t)
check(lim2[-1] is None and sum(1 for a,b in zip([lim[-1]]+lim2,lim2) if a and not b)==1,"a calm spell well below the level lifts it once")
acts=" | ".join(a["msg"] for a in g.activity)
check("FloodGuard: the radio is" in acts and "quiet again" in acts,"Activity says when it started and lifted")
# 3. just under the lift line doesn't lift (recovery margin): 15 (above 0.7*20=14) keeps it on
g=setup(); t0=time.time()
lim,_=run(g,[30]*12+[15]*120,t0)
check(lim[-1] is not None,"busy just under the level isn't calm enough to lift it")
# 4. tightening is logged and steps at most every two minutes
g=setup(); t0=time.time()
lim,_=run(g,[45]*60,t0)
steps=sum(1 for a,b in zip(lim,lim[1:]) if a and b and b<a)
check(steps>=1 and "now held back too" in " ".join(a["msg"] for a in g.activity) or "counted too" in " ".join(a["msg"] for a in g.activity),"tightening is written to Activity")
gaps=[i for i,(a,b) in enumerate(zip(lim,lim[1:])) if a and b and b<a]
check(all(y-x>=12 for x,y in zip(gaps,gaps[1:])),"at most one step every two minutes: %s"%gaps)
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
