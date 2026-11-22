# "Look after itself": one tap turns on what lets a repeater be left alone, and then each part does its job without
# anyone at the page: Monitor to Protect, the level following its suggestion (early ones only up to a cap), route
# blocks without asking, the evidence log the suggestion needs, and updates where the install can update itself.
# All names, routes and versions are made up.
import logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
T0=time.time()
SAVE=sg.IN_PLUGIN
sg.IN_PLUGIN=True   # an install that can update itself
real_managed=sg.managed_update

def fresh(**over):
    m=mock(); g=guard(m, mode="monitor", floodguard=False, **over)
    g.settings.pop("mode",None); g.settings["mode"]="monitor"; g.rebuild_cfg()
    return m,g

# --- the offer
m,g=fresh()
f=g.set_forget_status()
check(f["offer"] and not f["on"],"a new install is offered it")
check(set(f["missing"])=={"level_auto","level_auto_early","evidence_log","route_auto","auto_update"},"and is missing what acts without asking: %s"%f["missing"])
check(f["turn_on"].get("set_forget_prompt") is False,"answering it puts the offer away")
check(g.status()["set_forget"]["offer"] is True,"the page is told")
sg.managed_update=lambda: "Updated by Docker"
f2=g.set_forget_status()
check(not f2["can_update"] and "auto_update" not in f2["turn_on"],"where updates are handled elsewhere, they're left out")
sg.managed_update=real_managed
g.cfg["update_check"]="off"
check("auto_update" not in g.set_forget_status()["turn_on"],"and while looking for versions is off")
g.cfg["update_check"]="daily"
g.settings["paused"]=True; g.rebuild_cfg()
check(not g.set_forget_status()["offer"],"not offered while paused")
g.settings["paused"]=False; g.rebuild_cfg()

# Not now: nothing changes but the offer
m,g=fresh()
before={k:g.cfg.get(k) for k in ("level_auto","route_auto","auto_update","evidence_log","level_auto_early")}
g.apply_settings({"set_forget_prompt":False,"auto_update_prompt":False})
check(not g.set_forget_status()["offer"],"Not now: offer gone")
check(before=={k:g.cfg.get(k) for k in before},"and nothing else changed")

# --- turning it on
m,g=fresh()
r=g.apply_settings(g.set_forget_status()["turn_on"])
f=g.set_forget_status()
check(f["on"] and not f["offer"],"one tap: everything on, offer gone")
check(all(g.cfg.get(k) is True for k in ("auto_protect","level_auto","level_auto_early","evidence_log","route_auto","auto_update")),"each part is on")
check("look after itself" in (r.get("message") or ""),"it says so: %s"%r)
check(any("look after itself" in a["msg"] for a in g.activity),"and in Activity")
check(g.evidence is not None,"the evidence log starts at once")
check(g.cfg["level"]==50 and g.cfg["mode"]=="monitor","the level and mode are not touched by the tap itself")
sf_cfg=dict(g.settings)

# --- day 1: Monitor switches itself to Protect
g.monitor_since=T0-25*3600
for i in range(12): g.catches.append(T0-3600+i)
g._auto_checked=0; g._maybe_auto_protect()
check(g.cfg["mode"]=="protect","after a day with spam it is protecting, with nobody there")

# --- the level follows its suggestion, an early (unmarked) one only up to 70
g.advisor=lambda: {"families":[{"key":"level","ready":True}]}
g.preview_summary=lambda: {"suggested":70,"levels":[1],"early":True}
g._maybe_auto_level(T0); check(g.cfg["level"]==60,"an early suggestion is followed: %s"%g.cfg["level"])
g._maybe_auto_level(T0+2000); check(g.cfg["level"]==70,"up to 70")
g.preview_summary=lambda: {"suggested":90,"levels":[1],"early":True}
for i in range(5): g._maybe_auto_level(T0+4000+i*2000)
check(g.cfg["level"]==70,"never past 70 while nothing is marked: %s"%g.cfg["level"])
g.preview_summary=lambda: {"suggested":90,"levels":[1],"early":False}
for i in range(5): g._maybe_auto_level(T0+20000+i*2000)
check(g.cfg["level"]==80,"once marks make it firm, up to the ceiling of 80: %s"%g.cfg["level"])
g.preview_summary=lambda: {"suggested":40,"levels":[1],"early":False}
g._maybe_auto_level(T0+40000); check(g.cfg["level"]==80,"a quiet spell doesn't loosen it at once")
g._maybe_auto_level(T0+40000+3*86400+60); check(g.cfg["level"]==75,"after three days it eases off: %s"%g.cfg["level"])
for d in range(4,12): g._maybe_auto_level(T0+40000+d*86400+60)
check(g.cfg["level"]==40,"and keeps easing a step a day to the suggestion: %s"%g.cfg["level"])
# an early guess never eases it below Balanced, whatever it suggests (unmarked traffic often suggests the gentlest)
m3,g3=fresh(); g3.apply_settings(g3.set_forget_status()["turn_on"]); g3.apply_settings({"mode":"protect"})
g3.advisor=lambda: {"families":[{"key":"level","ready":True}]}
g3.preview_summary=lambda: {"suggested":70,"levels":[1],"early":True}
g3._maybe_auto_level(T0); g3._maybe_auto_level(T0+2000); check(g3.cfg["level"]==70,"firmed up during heavy spam")
g3.preview_summary=lambda: {"suggested":0,"levels":[1],"early":True}
for d in range(0,15): g3._maybe_auto_level(T0+3000+d*86400+60)
check(g3.cfg["level"]==50,"then eases back to Balanced and no further: %s"%g3.cfg["level"])
g3.level_preview={}; g3.apply_settings({"level":40,"level_auto":True})
for d in range(16,30): g3._maybe_auto_level(T0+3000+d*86400+60)
check(g3.cfg["level"]==40,"a gentler level you chose is left alone by a guess: %s"%g3.cfg["level"])
# without Look after itself, an early guess still isn't followed
m2,g2=fresh(); g2.settings.update({"level_auto":True,"mode":"protect"}); g2.rebuild_cfg()
g2.advisor=lambda: {"families":[{"key":"level","ready":True}]}
g2.preview_summary=lambda: {"suggested":70,"levels":[1],"early":True}
g2._maybe_auto_level(T0); check(g2.cfg["level"]==50,"Auto level on its own still waits for marks")

# --- route surges are blocked without asking, a few at a time, and end by themselves
m,g=fresh(known_min_msgs=3); g.apply_settings(g.set_forget_status()["turn_on"]); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all","Nice and clear","Anyone about"]):
    m.add("Quarry Pete",t,["BA","AA","DE"],ago=3000-i*60)
for r in range(5):
    for i in range(9): m.add(f"V{r}x{i:02d}",f"Hello {r} {i}",[f"B{r}",f"A{r}","DE"],ago=1500-i*40)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
auto=[b for b in g.blocks.values() if b.get("source")=="route-auto"]
check(1<=len(auto)<=3,"surging routes blocked without asking, at most three: %d"%len(auto))
check(not any(b.get("source")=="route-auto" and "BA" in str(b.get("value")) for b in g.blocks.values()),"the regular's route is left alone")
check(m.decide("Quarry Pete","Back again",["BA","AA","DE"])=="allow","a known person still gets through")
end=max(b["expires"] for b in auto)
g._expire_blocks(end+1)
check(not [b for b in g.blocks.values() if b.get("source")=="route-auto"],"and every one ends by itself")

# --- updates install by themselves once a version has been out a while
m,g=fresh(); g.apply_settings(g.set_forget_status()["turn_on"])
newer=".".join(str(int(x)+(1 if i==0 else 0)) for i,x in enumerate(sg.VERSION.split(".")))
called=[]
g.update_action=lambda op,body: called.append((op,body)) or {"ok":True}
g.update_info={"latest":newer,"published":time.time()-600}; g._maybe_auto_update()
check(not called,"a version just out is left a while first")
g.update_info={"latest":newer,"published":time.time()-3*3600}; g._maybe_auto_update()
check(called==[("install_update",{"version":newer})],"then installed, with nobody pressing anything")
g._maybe_auto_update(); check(len(called)==1,"once")

# --- people: regulars are learnt and settle with nobody marking anything
m,g=fresh(known_min_msgs=3, known_min_minutes=60); g.apply_settings(g.set_forget_status()["turn_on"]); g.apply_settings({"mode":"protect"})
for i in range(4): m.add("Hilltop Mo",f"Evening all {i}",["C1","DE"],ago=5000-i*900)
g.poll_once()
check(g.is_known("Hilltop Mo"),"a regular becomes known by themselves")
g.known["Hilltop Mo"]=[time.time()-8*86400,time.time(),12]
check(g.settled("Hilltop Mo"),"and settled after a week")
for i in range(12): m.add("Same Again Sid","Buy cheap crypto at q.example now",["C1","DE"],ago=600-i*30)
g.poll_once(); g.poll_once()
check(g.repeat_offender("Same Again Sid") or any(b.get("who")=="Same Again Sid" for b in g.blocks.values()),"someone repeating themselves is dealt with without you")

# --- you take the level back: Auto level stops, and the offer doesn't nag
m,g=fresh(); g.apply_settings(g.set_forget_status()["turn_on"])
g.level_preview={}; g.apply_settings({"level":60})
check(not g.cfg["level_auto"],"setting the level yourself stops Auto level")
check(not g.set_forget_status()["offer"],"and the offer doesn't come back")
# starting again from scratch offers it again for what was reset
g.apply_settings({"reset":True})
f=g.set_forget_status()
check(f["offer"] and "route_auto" in f["missing"] and "auto_update" not in f["missing"],"after a reset it's offered again for what was cleared: %s"%f["missing"])

sg.IN_PLUGIN=SAVE
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
