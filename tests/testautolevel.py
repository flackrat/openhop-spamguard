# 6.27.3: Auto level follows the level suggestion in small steps, tightens quickly and loosens slowly, never goes past
# its ceiling, holds still after a message marked fine, steps back once after a tightening was followed by one, and
# stops when you set the level yourself. All names are made up.
import sys, time, logging
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
    g.preview_summary=lambda: {"suggested":sug,"levels":[1],"early":False}
    return g
T0=time.time()

# off by default: nothing moves
m=mock(); g=guard(m, floodguard=False); g.advisor=lambda: {"families":[{"key":"level","ready":True}]}; g.preview_summary=lambda: {"suggested":90,"levels":[1],"early":False}
g._maybe_auto_level(T0); check(g.cfg["level"]==50 and not g.cfg.get("level_auto"),"off by default: the level does not move")

# tightens in steps of ten, up to the suggestion
g=make(50,70)
g._maybe_auto_level(T0); check(g.cfg["level"]==60,"first step is ten points: %s"%g.cfg["level"])
g._maybe_auto_level(T0+700); check(g.cfg["level"]==60,"not again within half an hour")
g._maybe_auto_level(T0+2000); check(g.cfg["level"]==70,"then on to the suggestion")
g._maybe_auto_level(T0+4000); check(g.cfg["level"]==70,"and it stops there")

# the ceiling
g=make(70,95)
for i in range(6): g._maybe_auto_level(T0+i*2000)
check(g.cfg["level"]==80,"never above the ceiling of 80: %s"%g.cfg["level"])
g=make(70,95,level_auto_max=90)
for i in range(6): g._maybe_auto_level(T0+i*2000)
check(g.cfg["level"]==90,"a higher ceiling is respected: %s"%g.cfg["level"])

# loosens slowly: only after the gentler suggestion has lasted three days, then five points a day
g=make(60,30)
g._maybe_auto_level(T0); check(g.cfg["level"]==60,"a lower suggestion does not loosen at once")
g._maybe_auto_level(T0+2*86400); check(g.cfg["level"]==60,"nor after two days")
g._maybe_auto_level(T0+3*86400+60); check(g.cfg["level"]==55,"after three days it loosens by five: %s"%g.cfg["level"])
g._maybe_auto_level(T0+3*86400+1000); check(g.cfg["level"]==55,"and not again the same day")
g._maybe_auto_level(T0+4*86400+2000); check(g.cfg["level"]==50,"but the next day it does")
g=make(60,30)
g._maybe_auto_level(T0); g.preview_summary=lambda: {"suggested":60,"levels":[1],"early":False}; g._maybe_auto_level(T0+2*86400)
g.preview_summary=lambda: {"suggested":30,"levels":[1],"early":False}; g._maybe_auto_level(T0+3*86400+1000)
check(g.cfg["level"]==60,"the wait starts again if the suggestion goes back up")

# holds still after a message marked fine
g=make(50,70); g.genuine_marks.append(T0-60)
g._maybe_auto_level(T0); check(g.cfg["level"]==50,"a message marked fine yesterday: no tightening")
# steps back once after a tightening was followed by a fine mark
g=make(50,80)
g._maybe_auto_level(T0); check(g.cfg["level"]==60,"tightened")
g.genuine_marks.append(T0+100)
g._maybe_auto_level(T0+800); check(g.cfg["level"]==55,"a fine mark after it: one step back: %s"%g.cfg["level"])
g._maybe_auto_level(T0+1500); check(g.cfg["level"]==55,"only once")

# not enough to go on
g=make(50,70); g.preview_summary=lambda: {"suggested":70,"levels":[1],"early":True}; g._maybe_auto_level(T0)
check(g.cfg["level"]==50,"an early guess is not followed")
g=make(50,70); g.advisor=lambda: {"families":[{"key":"level","ready":False}]}; g._maybe_auto_level(T0)
check(g.cfg["level"]==50 and g.auto_level_status()["waiting"],"not ready: nothing moves and it says why")

# you take over: setting the level yourself switches Auto off, and says so
g=make(50,70)
g.apply_settings({"level":40})
check(g.cfg["level"]==40 and not g.cfg.get("level_auto"),"setting the level yourself switches Auto off")
g._maybe_auto_level(T0+9999); check(g.cfg["level"]==40,"and it stays where you put it")
g=make(50,70); g.apply_settings({"level":40,"level_auto":True})
check(g.cfg.get("level_auto"),"switching it on and setting a level together keeps it on")
st=make(50,70).status()["level"]["auto"]
check(st["on"] and st["max"]==80,"the page is told about it")
print("testautolevel: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
