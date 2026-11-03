# The settings advisor: suggestions only, and only once the traffic has settled. Nothing here changes a setting.
# All names and messages are made up.
import sys, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

m=mock(); g=guard(m, floodguard=False)
a=g.advisor()
check(a["steady"] is False and a["days"]==0 and a["messages"]==0,"empty: not steady, nothing counted")
check(all(not f["suggestion"] for f in a["families"]),"empty: no suggestions")
check({f["key"] for f in a["families"]}=={"level","public_bots","text_sense","quick_resend_hold"},"four families")
check("Gathering" in a["families"][0]["status"],"the meter says it is gathering")

def fill(g, days, per_hour=6, spike=None):
    now=time.time()
    for h in range(int(days*24)):
        ts=now-h*3600-60
        hour=str(int(ts//3600*3600))
        g.hist[hour]={"m":per_hour,"c":0,"x":0,"g":0,"a":0.0,"h":{}}
fill(g,1)
check(g.advisor()["steady"] is False,"1 day is not enough")
fill(g,4)
a=g.advisor()
check(a["steady"] is True and a["days"]>=3,"4 flat days: steady")
# a big jump in the newest day moves the busy-time figure, so it is not steady
for h in range(0,24):
    g.hist[str(int((time.time()-h*3600-60)//3600*3600))]["m"]=60
check(g.advisor()["steady"] is False,"a sudden jump in the newest day: not steady yet")
fill(g,4)

# Public bots: off, count only (few and many), stopping
cfg=g.advisor()["families"][1]
check("Off" in cfg["status"] and not cfg["suggestion"],"bots off: says so, no suggestion")
g.apply_settings({"public_bots":True})
check(not g.advisor()["families"][1]["suggestion"],"bots count-only with none seen: no suggestion")
for i in range(6): g._hist_bump(time.time()-i*600,"pb")
s=g.advisor()["families"][1]["suggestion"]
check(s and s["set"]=={"public_bots_log_only":False},"six bots in 3 days: suggests stopping them, never does it")
check(g.cfg["public_bots_log_only"] is True,"the advisor changed nothing")
g.apply_settings({"public_bots_log_only":False})
check(not g.advisor()["families"][1]["suggestion"] and "Stopping" in g.advisor()["families"][1]["status"],"already stopping: no suggestion")

# Double sends: plenty of repeats and few retries suggests it; many retries does not
for i in range(12): g._hist_bump(time.time()-i*300,"rs")
s=g.advisor()["families"][3]["suggestion"]
check(s and s["set"]=={"quick_resend_hold":True},"12 double sends, 0 retries: suggests stopping them")
for i in range(8): g._hist_bump(time.time()-i*300,"rt")
check(not g.advisor()["families"][3]["suggestion"],"many retries: not suggested")
g.apply_settings({"quick_resend_hold":True})
check("Stopping repeats" in g.advisor()["families"][3]["status"],"on: says it is stopping")

# Reworded spam: needs marks first
f=g.advisor()["families"][2]
check("Off" in f["status"] and "Mark 5" in f["status"],"sense off, no marks: asks for marks")
for i in range(5): g.labels[f"k{i}"]="spam"
g.apply_settings({"text_sense":True})
f=g.advisor()["families"][2]
check("Nothing has looked like" in f["status"],"sense on, enough marks, nothing seen: nothing to act on")
for i in range(3): g._hist_bump(time.time()-i*600,"sw")
f=g.advisor()["families"][2]
check(f["suggestion"] and f["suggestion"]["set"] is None,"would-have-held seen: suggests reading the notes first, with no button")

# Reaches the status and the evidence record
check("advisor" in g.status() and g.status()["advisor"]["families"],"in the status")
ex=g.experiments_summary()
check(ex["public_bots_3d"]==6 and ex["sense_would_hold_3d"]==3 and ex["double_sends_3d"]==12 and ex["retries_3d"]==8,"experiment totals")
print("testadvisor: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
