# openHop's own advert limit on FloodGuard's page: read from openHop's config and statistics, shown only where this
# openHop has it, and switched on or off from the page through openHop's own setting. Made-up figures.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g=guard(mock())
calls=[]
CONF={"advert_rate_limit":{"enabled":False,"bucket_capacity":2,"refill_interval_seconds":36000},"advert_penalty_box":{"enabled":True}}
def fake(method,path,body=None,timeout=15):
    calls.append((method,path,body))
    if path=="/api/stats": return {"success":True,"data":{"local_hash":"5A","config":{"radio":{},"repeater":CONF}}}
    if path=="/api/advert_rate_limit_stats": return {"success":True,"data":{"stats":{"adverts_allowed":900,"adverts_dropped":40},"active_penalties":{"AB":10},"adaptive":{"current_tier":"normal"}}}
    if path=="/api/update_advert_rate_limit_config":
        CONF["advert_rate_limit"]["enabled"]=body["rate_limit_enabled"]; return {"success":True}
    return {"success":True,"data":{"policy_engine":{"enabled":True,"default_action":"allow","rules":[]},"groups":{}}}
g._api=fake
g.refresh_openhop_info(force=True)
a=g.fg_status()["oh_adverts"]
check(a["available"] and a["on"] is False and a["penalty"] and a["per_hours"]==10.0 and a["burst"]==2,"read from openHop's config: %s"%a)
check(a["allowed"]==900 and a["dropped"]==40 and a["penalties"]==1,"with its statistics")
r=g.action("oh_advert_limit",{"on":True})
check(("POST","/api/update_advert_rate_limit_config",{"rate_limit_enabled":True}) in calls,"switched on through openHop's own setting")
check(g.fg_status()["oh_adverts"]["on"] and any("advert limit switched on" in x["msg"] for x in g.activity),"shown as on, and written to Activity")
g.refresh_openhop_info(force=True)
check(g.fg_status()["oh_adverts"]["on"] is True,"and read back from openHop")
# an openHop without it: nothing shown
g2=guard(mock()); g2._api=lambda m,p,b=None,timeout=15: {"success":True,"data":{"config":{"repeater":{}}}} if p=="/api/stats" else {"data":[]}
g2.refresh_openhop_info(force=True)
check(g2.fg_status()["oh_adverts"]=={"available":False},"an openHop without it: not offered")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
