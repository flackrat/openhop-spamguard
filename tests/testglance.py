# Protection at a glance, freshness per part, the settings change history, and "why it got through" on spam you
# mark that wasn't stopped. Display only: nothing here changes what is blocked. Made-up names and messages only.
import sys, logging, time, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once(); g.loop_beat=time.time()   # the run loop sets this
# --- protection at a glance
g.apply_settings({"mode":"monitor"}); p=g.protection()
check(p["state"]=="watch","Monitor is watching only: %s"%p["state"])
check({x["part"] for x in p["parts"]}>={"mode","openhop","check","rules","sync","floodguard"},"the parts that decide it are listed")
g.apply_settings({"mode":"protect"}); g.poll_once(); g.loop_beat=time.time()
p=g.protection(); check(p["state"]=="ok" and p["line"]=="Protected","Protect with openHop answering and rules confirmed: %s %s"%(p["state"],p.get("why")))
rules=next(x for x in p["parts"] if x["part"]=="rules"); check(rules["state"]=="ok" and rules["ts"],"rules confirmed, with when")
g.apply_settings({"paused":True}); p=g.protection()
check(p["state"]=="bad" and "Not protected" in p["line"],"paused is not protected")
g.apply_settings({"paused":False})
g.rules_seen=(g.rules_expected or 0)+1; p=g.protection()
check(p["state"]=="partly","rules that don't match openHop's need a look")
g.rules_seen=g.rules_expected
g.loop_beat=time.time()-600; p=g.protection()
check(p["state"]=="bad" and "Checking" in (p["why"] or ""),"checking stopped is not protected, and says why: %s"%p.get("why"))
g.loop_beat=time.time()
st=g.status(); check("protection" in st and st["protection"]["state"]=="ok","the Overview gets it in status")
# --- freshness
f={x["part"]:x for x in g.health()["fresh"]}
check(set(f)>={"packets","check","neighbours","radio","rules","sync","save"},"every part has a freshness line")
check(f["check"]["state"]=="ok" and f["rules"]["state"]=="ok","checks and rules are fresh")
g.rules_checked=time.time()-3600; f={x["part"]:x for x in g.health()["fresh"]}
check(f["rules"]["state"]=="late","an hour since rules were checked is late")
# --- settings history
g.settings_history.clear(); g._hist_last=None; g.rebuild_cfg()
check(not g.settings_history,"the first look only sets the starting point")
g.apply_settings({"level":70})
h=list(g.settings_history); check(h and h[0]["key"]=="level" and h[0]["old"].startswith("50") and h[0]["new"].startswith("70")
    and h[0]["by"]=="You, on the page","a level change by you is recorded with before and after: %s"%h[:1])
g.apply_settings({"mode":"monitor"})
check(g.settings_history[0]["label"]=="Mode" and g.settings_history[0]["new"]=="Monitor only","mode changes read in words")
g.apply_settings({"reset":True})
check(any(x.get("new","").endswith("(default)") for x in list(g.settings_history)[:5]) or g.settings_history[0]["key"]=="level",
      "settings put back are recorded")
n=len(g.settings_history); g.rebuild_cfg(); g.rebuild_cfg()
check(len(g.settings_history)==n,"nothing recorded when nothing changed")
before=len(g.settings_history)
sg._set_hist_who("Auto level"); g.settings["level"]=40; g.rebuild_cfg(); sg._set_hist_who(None)
check(len(g.settings_history)==before+1 and g.settings_history[0]["by"]=="Auto level","automatic changes say who made them")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(len(g2.settings_history)==len(g.settings_history) and g2.settings_history[0]["by"]=="Auto level","history survives a restart")
check(len(g2.settings_history)==len(g.settings_history),"and a restart itself isn't a change")
for i in range(sg.SETTINGS_HISTORY_MAX+20):
    g.apply_settings({"level":30+i%2})
check(len(g.settings_history)==sg.SETTINGS_HISTORY_MAX,"kept to the last %d"%sg.SETTINGS_HISTORY_MAX)
check(len(g.status()["settings_history"])==100,"the page gets the newest 100")
# --- why it got through
m2=mock(); g3=guard(m2); g3.poll_once()
m2.add("Quarry Newbie","Win a free radio, reply now please",["A1","B2"],ago=10)
g3.poll_once()
e=[x for x in g3.events if x.sender=="Quarry Newbie"][0]
w=g3.why_through({"packet":e.packet,"sender":e.sender,"text":e.text})
check(w and "first sighting" in w,"a first message from a new name: %s"%w)
r=g3.action("label",{"packet":e.packet,"sender":e.sender,"text":e.text,"label":"spam"})
check("first sighting" in r["message"],"and the answer says so: %s"%r["message"])
g3.watch_channels.add("Public")
check("Count only" in (g3.why_through({"packet":e.packet}) or ""),"a Count only channel is the reason when it applies")
g3.watch_channels.discard("Public")
g3.allow_senders.add("Quarry Newbie")
check("trusted" in (g3.why_through({"packet":e.packet}) or ""),"a trusted name is the reason when it applies")
g3.allow_senders.discard("Quarry Newbie")
g3.apply_settings({"paused":True}); check("paused" in g3.why_through({"packet":e.packet}),"paused says so")
g3.apply_settings({"paused":False})
e.matched="text:x"; g3.apply_settings({"mode":"monitor"})
check("Monitor only" in g3.why_through({"packet":e.packet}),"spotted but on Monitor says Protect would stop it")
g3.apply_settings({"mode":"protect"})
check(g3.why_through({"packet":e.packet}) is None,"nothing to explain when it was stopped")
check(g3.why_through({"packet":"nope"}) is None,"nothing said about a message it no longer has")
# --- openHop's own mode
m4=mock(); g4=guard(m4); g4.apply_settings({"mode":"protect"}); g4.poll_once(); g4.loop_beat=time.time()
check(g4.oh_mode is None and g4.protection()["state"]!="idle","openHop's mode not known: nothing said")
m4.oh_mode="no_tx"; g4.oh_mode_ts=0; g4.refresh_oh_mode()
p=g4.protection(); rp=next(x for x in p["parts"] if x["part"]=="repeating")
check(g4.oh_mode=="no_tx" and p["state"]=="idle" and "isn't repeating" in p["line"],"openHop on No TX: nothing to stop: %s"%p["line"])
check("No TX" in rp["text"] and rp["state"]=="warn","the part says No TX")
check(g4.status()["openhop_mode"]=="no_tx","the page gets openHop's mode")
m4.oh_mode="monitor"; g4.oh_mode_ts=time.time(); g4.refresh_oh_mode()
check(g4.oh_mode=="no_tx","read at most every two minutes")
g4.oh_mode_ts=0; g4.refresh_oh_mode(); check(g4.oh_mode=="monitor","then picks up the change")
m4.oh_mode="forward"; g4.oh_mode_ts=0; g4.refresh_oh_mode()
check(g4.protection()["state"]=="ok","back on Repeater: protected again")
print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
