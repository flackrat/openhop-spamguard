# Updates that don't finish are written to Activity with the reason; an automatic install is tried three times,
# twenty minutes apart, then again a day later; the Overview says when the last try didn't finish; and an automatic
# install isn't recorded as "requested from the web page". Made-up versions.
import time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
SAVE=sg.IN_PLUGIN; sg.IN_PLUGIN=True
m=mock(); g=guard(m, floodguard=False, auto_update=True)
newer=".".join(str(int(x)+(1 if i==0 else 0)) for i,x in enumerate(sg.VERSION.split(".")))
T=time.time()
g.update_info={"latest":newer,"published":T-3*3600}
started=[]
def fake_start(want,force=False,auto=False):
    started.append((want,auto)); g.plugin_update={"state":"running","version":want,"auto":auto,"ts":time.time(),"pct":2,"lines":[]}
    g._update_step("Update failed: could not reach openHop's plugin installer", state="failed")
    return {"ok":True}
g.start_plugin_update=fake_start
g._maybe_auto_update()
check(started==[(newer,True)],"tried automatically, marked as automatic")
acts=[a["msg"] for a in g.activity]
check(not any("requested from the web page" in a for a in acts),"not recorded as a request from the page")
check(any("didn't finish (automatic)" in a and "plugin installer" in a for a in acts),"the failure and its reason are in Activity: %s"%acts[-1:])
check(g.auto_update_due(T+60) is None,"not again straight away")
check(g.auto_update_due(T+1300)==newer,"tried again after twenty minutes")
g.auto_update_tried["ts"]-=1300; g._maybe_auto_update(); check(g.auto_update_tried["tries"]==2,"second try counted")
g.auto_update_tried["ts"]=time.time()-1300; g._maybe_auto_update(); check(g.auto_update_tried["tries"]==3,"third")
check(g.auto_update_due(time.time()+1300) is None,"after three tries it waits a day")
check(g.auto_update_due(time.time()+86500)==newer,"then tries again")
check(sum("didn't finish" in a["msg"] for a in g.activity)==3,"each failure written once")
# a press on the page is still recorded as such
g.start_plugin_update=lambda want,force=False,auto=False: (g.note(f"Update to v{want} requested from the web page") if not auto else None) or {"ok":True}
g.update_action("install_update",{"version":newer})
check(any("requested from the web page" in a["msg"] for a in g.activity),"a press on the page says so")
# the try count survives a restart
g._save_state(force=True)
g2=sg.SpamGuard(dict(g.file_cfg, state_file=g.cfg["state_file"]))
check(g2.auto_update_tried.get("tries")==3,"try count kept across a restart")
sg.IN_PLUGIN=SAVE
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
