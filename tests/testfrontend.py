# As a plugin, SpamGuard puts openHop's own dashboard back if its doorway page is picked as openHop's
# main web page; and Health only mentions openHop's speed fix when openHop is actually behind.
import sys
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m)
calls=[]; sel={"id":"plugin:openhop-spamguard"}
def api(method, path, body=None, timeout=None):
    calls.append((method,path,body))
    if path=="/api/web_frontends": return {"success":True,"data":{"selected_id":sel["id"]}}
    if path=="/api/update_web_config": sel["id"]="builtin"; return {"success":True}
    return {}
real=g._api; g._api=api
sg.IN_PLUGIN=True
g._maybe_guard_frontend()
check(("POST","/api/update_web_config",{"web":{"web_path":None}}) in calls,"switches openHop back to its own dashboard")
check(any("dashboard back" in n["msg"] for n in g.activity),"notes it in Activity")
calls.clear(); g._maybe_guard_frontend(); check(not calls,"checks at most once a minute")
g._frontend_checked=0; g._maybe_guard_frontend()
check(not any(c[1]=="/api/update_web_config" for c in calls),"leaves openHop alone when its own dashboard is selected")
sg.IN_PLUGIN=False; g._frontend_checked=0; calls.clear(); g._maybe_guard_frontend()
check(not calls,"only the plugin does this")
g._api=real
# speed fix warning only when openHop is behind
sg.IN_PLUGIN=True
g._fix_cache=(sg.time.time(), False)
g.lag_samples.clear()
check(not any("speed fix" in w for w in g.health()["warnings"]),"no speed-fix nag while openHop keeps up")
now=sg.time.time()
for i in range(5): g.lag_samples.append((now-i, 120))
check(any("speed fix" in w for w in g.health()["warnings"]),"speed fix suggested when openHop is minutes behind")
sg.IN_PLUGIN=False
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
