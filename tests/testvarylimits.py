# Each repeater shifts some limits a little around its level, from its own private id and the week: the same all
# week and after a restart, different on other repeaters and next week, always inside each setting's range and
# in a safe order, and never touching a value you set yourself.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def make(**kw):
    m=mock(); return guard(m, vary_limits=True, **kw)
g1=make(); g2=make()
check(g1.instance_id!=g2.instance_id, "two installs have different private ids")
k=list(sg.SpamGuard.VARY)
v1={x:g1.cfg[x] for x in k}; v2={x:g2.cfg[x] for x in k}
lv=sg.level_values(50)
check(v1!=v2 or any(v1[x]!=lv[x] for x in k), f"limits differ between repeaters at the same level: {v1} {v2}")
g1b=sg.SpamGuard(dict(g1.file_cfg)); check({x:g1b.cfg[x] for x in k}==v1, "the same all week, including after a restart")
now=time.time()
nxt=g1.varied_values({**sg.DEFAULT_CONFIG,**lv}, now+7*86400)
check(nxt!=g1.varied_values({**sg.DEFAULT_CONFIG,**lv}, now), "next week they shift again")
# ranges and order, across many repeaters and every level
bad=[]
import random as _r
f=g1
for i in range(300):
    f._instance_id="%012x"%_r.getrandbits(48)
    for l in (0,25,50,75,88,100):
        base={**sg.DEFAULT_CONFIG,**sg.level_values(l)}
        v={**base,**f.varied_values(base,now)}
        for x in k:
            m=sg.META_BY_KEY[x]
            if not (m.get("min",v[x])<=v[x]<=m.get("max",v[x])): bad.append((x,v[x]))
        if not (v["repeat_max"]<v["name_budget_max"] and v["name_budget_max"]>=8): bad.append(("budget",l))
        if v["slow_repeat_window_seconds"]<v["slow_repeat_hold_seconds"]: bad.append(("slow",l))
        if v["repeat_block_seconds"]>v["block_ttl_seconds"]: bad.append(("ttl",l))
        if abs(v["known_min_minutes"]-base["known_min_minutes"])>0.25*base["known_min_minutes"]+1: bad.append(("known",l))
check(not bad, f"always in range and in a safe order: {bad[:5]}")
# your own values win, and it can be turned off
g3=make(repeat_max=7); check(g3.cfg["repeat_max"]==7, "a value you set yourself is never shifted")
g4=make(); g4.file_cfg.pop("known_min_minutes",None); g4.apply_settings({"vary_limits":False}); check(all(g4.cfg[x]==sg.level_values(50)[x] for x in k), "turned off, the level's exact values are used")
check(sg.DEFAULT_CONFIG["vary_limits"] is True and any(m["key"]=="vary_limits" for m in sg.SETTINGS_META), "on by default, and shown as a setting")
g5=make(); g5.file_cfg.pop("known_min_minutes",None); g5.rebuild_cfg()
check(not g5.own_level_values(), "shifted values are not mistaken for your own settings")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
