# 6.55.0: route checks (experimental, off by default, transmits). A trace follows the spam's own route out to one
# exact repeater, named by 4 bytes of its key, and back; only at night, only with the radio quiet, under an hourly
# limit, once a week per pair; nothing is sent until openHop offers route traces. Made-up keys and names only.
import sys, os, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
lt=time.localtime(); night=time.mktime((lt.tm_year,lt.tm_mon,lt.tm_mday,3,0,0,0,0,-1)); day=night+9*3600
m=mock(); g=guard(m); g.poll_once()
K1="B6AA00110000000000000000000000000000000000000000000000000000AA01"; K2="B6BB00220000000000000000000000000000000000000000000000000000BB02"
N04="04CC00330000000000000000000000000000000000000000000000000000CC03"; NE="EECC00440000000000000000000000000000000000000000000000000000CC04"
g.adv_routes[K1+"|63"]=[5,time.time(),40.0,-95.0,"Quarry North"]; g.adv_routes[K2+"|27"]=[5,time.time(),40.5,-96.0,"Quarry South"]; g._adv_stamp+=1
learned={("04","EE"):{"key":N04,"name":"Quarry Four","lat":40.1,"lon":-95.1},("EE","ME"):{"key":NE,"name":"Quarry Edge","lat":40.2,"lon":-95.2}}
g._learned=lambda: learned
g._geo={"ts":time.time(),"ent":{"entries":[{"kind":"area","code":"B6","code_check":{"verdict":"made_up"},"routes":[{"path":"B6>04>EE","n":30}]}]}}
plan=g.route_check_plan()
check(len(plan)==2 and {p["key"][:8] for p in plan}=={"B6AA0011","B6BB0022"},"each repeater using the code is checked against where the spam entered: %s"%[p["pair"] for p in plan])
check(plan[0]["path"]==["EECC0044","04CC0033",plan[0]["key"][:8],"04CC0033","EECC0044"],"the trace goes out along the spam's route, to one exact repeater, and back: %s"%plan[0]["path"])
check(g.route_check_step(night) is None and not getattr(m,"traces",[]),"off by default: nothing is sent")
g.apply_settings({"route_checks":True}); g.fg["busy_now"]=3.0
check(g.route_check_step(day) is None and not getattr(m,"traces",[]),"not during the day")
g.fg["busy_now"]=25.0; check(g.route_check_step(night) is None,"not while the radio is busy")
g.fg["busy_now"]=None; check(g.route_check_step(night) is None,"not when how busy it is isn't known")
g.fg["busy_now"]=3.0
check(g.route_check_step(night) is None and len(m.traces)==1 and g.route_check_state["api"] is False,"openHop without route traces: one try, then nothing")
check(g.route_check_step(night+60) is None and len(m.traces)==1,"and it doesn't ask again the same day")
check(g.status()["route_checks"]["api"] is False,"the page says openHop doesn't offer it yet")
m.trace=lambda body:{"success":True,"data":{"complete":body["path"][2]=="B6AA0011","snr":[6.5,4.0,-3.25,4.0,6.0]}}
g.route_check_state["api_ts"]=0
r=g.route_check_step(night+120); check(r and r["ok"] and r["key"].startswith("B6AA"),"the first repeater answers: it is next to where the spam entered")
check(m.traces[-1]["hash_bytes"]==4,"named by 4 bytes of its key")
r=g.route_check_step(night+180); check(r and not r["ok"],"the other doesn't")
check(g.route_check_step(night+240) is None,"the hourly limit holds (2 by default)")
check(g.route_check_plan()==[],"each pair is checked once a week")
cc=g.code_check("B6",["04"]); check(cc["verdict"]=="next" and cc["next_to"][0]["confirmed"],"a confirmed check names that repeater as next to it: %s"%cc)
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg)); check(len(g2.probe_results)==2,"results survive a restart")
st=g.status()["route_checks"]; check(st["on"] and len(st["recent"])==2,"the page lists them")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
