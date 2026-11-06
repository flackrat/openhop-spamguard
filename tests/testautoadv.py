# 6.28.0: Auto level under misleading input. Fake "fine" marks, a flapping suggestion, a mark storm, a clock that
# goes backwards and random input must never push the level past its limits or make it swing. All names are made up.
import sys, time, random, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def make(level=50, sug=70, **over):
    m=mock(); g=guard(m, floodguard=False, level=level, level_auto=True, **over)
    g.apply_settings({"mode":"protect"}); g.settings["level"]=level; g.settings["level_auto"]=True; g.rebuild_cfg()
    g.advisor=lambda: {"families":[{"key":"level","ready":True}]}
    g.cur=[sug]
    g.preview_summary=lambda: {"suggested":g.cur[0],"levels":[1],"early":False}
    return g
T0=time.time(); DAY=86400

# 1. Someone sends fake "fine" marks all day, every day, while the real suggestion is to tighten.
#    The most this can do is stop the tightening: it can never loosen the level.
g=make(50,80)
for d in range(30):
    for k in range(24):
        g.genuine_marks.append(T0+d*DAY+k*3600)
        g._maybe_auto_level(T0+d*DAY+k*3600+60)
check(g.cfg["level"]>=50,"endless fake fine marks never loosen the level (now %s)"%g.cfg["level"])

# 2. A fine mark right after each tightening: one step back each time, but the level still cannot go below where it began
g=make(50,80); lvl=[]
for i in range(40):
    t=T0+i*2000
    g._maybe_auto_level(t); g.genuine_marks.append(t+100); g._maybe_auto_level(t+900); lvl.append(g.cfg["level"])
check(min(lvl)>=45,"marks timed to follow each tightening cannot drag it below 5 under where it began (min %s)"%min(lvl))
check(max(lvl)<=80,"and it never goes above the ceiling (max %s)"%max(lvl))

# 2b. After one tightening, a run of fine marks over a day steps back once, not once per mark
g=make(50,80); g._maybe_auto_level(T0)
for k in range(1,12):
    g.genuine_marks.append(T0+k*700); g._maybe_auto_level(T0+k*700+650)
check(g.cfg["level"]==55,"eleven fine marks after one tightening: one step back only (now %s)"%g.cfg["level"])

# 3. A suggestion that flaps every 11 minutes for ten days: tightening is allowed, loosening needs three steady days
g=make(40,0); seen=[g.cfg["level"]]
for i in range(int(10*DAY/660)):
    g.cur[0]=95 if i%2==0 else 0
    g._maybe_auto_level(T0+i*660); seen.append(g.cfg["level"])
check(all(b>=a for a,b in zip(seen,seen[1:])),"a flapping suggestion never makes the level go down")
check(max(seen)<=80,"and never past the ceiling")

# 4. Mark storm: thousands of marks at once don't break anything
g=make(50,70)
for i in range(5000): g.genuine_marks.append(T0-30)
try:
    g._maybe_auto_level(T0); good=True
except Exception as e:
    good=False; print(e)
check(good and g.cfg["level"]==50,"a storm of fine marks just holds the level still")

# 5. A clock that jumps backwards does not crash or move the level wildly
g=make(50,70); g._maybe_auto_level(T0)
before=g.cfg["level"]
try:
    g._maybe_auto_level(T0-5*DAY); g._maybe_auto_level(T0-5*DAY+10); good=True
except Exception as e:
    good=False; print(e)
check(good and abs(g.cfg["level"]-before)<=10,"time going backwards moves it by at most one step (%s -> %s)"%(before,g.cfg["level"]))

# 6. Random input for a simulated month: steps stay inside the limits
for seed in range(8):
    rnd=random.Random(seed); g=make(rnd.randint(0,60),50); lastup=lastdown=-1e18; prev=g.cfg["level"]; bad=[]
    t=T0
    for i in range(3000):
        t+=rnd.choice([30,300,900,1800,3600,7200])
        g.cur[0]=rnd.randint(0,100)
        if rnd.random()<0.05: g.genuine_marks.append(t-rnd.randint(0,600))
        g._maybe_auto_level(t); now=g.cfg["level"]
        if now>prev:
            if now-prev>10: bad.append(("big up",prev,now))
            if t-lastup<1800: bad.append(("up too soon",t-lastup))
            lastup=t
        elif now<prev:
            if prev-now>5: bad.append(("big down",prev,now))
            lastdown=t
        if now>80: bad.append(("ceiling",now))
        prev=now
    check(not bad,"seed %d: every step is within the limits %s"%(seed,bad[:3]))
print("testautoadv: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
