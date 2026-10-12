# Per-channel counts behind the Overview's channel picker. All names and messages are made up.
import sys, logging, time, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m)
g.apply_settings({"mode":"protect"})
tag=sg.hashtag_secret("trailchat")
g.action("add_channel",{"name":"#trailchat","key":tag})
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=3000)
m.add("Canal Boat Ted","Anyone on the towpath tonight?",["A7","2F"],ago=2900,key=tag)
m.add("Base Camp 3","Radio check please",["B1","2F"],ago=2800,key=tag)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for i in range(8): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D"],ago=200-i)
g.poll_once(); g.poll_once()
mt=g.metrics(); ch=mt.get("channels") or {}
check(set(ch)>={"Public","#trailchat"},"both channels listed: "+str(list(ch)))
check(list(ch)[0]=="Public","Public listed first")
tot_m=sum(r["m"] for r in mt["hourly"]); per_m=sum(sum(r["m"] for r in c["hourly"]) for c in ch.values())
check(tot_m==per_m and tot_m>0,f"channel message counts add up to the total: {per_m} vs {tot_m}")
for f in ("c","x"):
    a=sum(r[f] for r in mt["daily"]); b=sum(sum(r[f] for r in c["daily"]) for c in ch.values())
    check(a==b,f"daily {f} adds up: {b} vs {a}")
check(sum(r["m"] for r in ch["#trailchat"]["hourly"])==2,"two messages on #trailchat")
pub_spam=sum(r["c"]+r["x"] for r in ch["Public"]["hourly"])
check(pub_spam>0 and sum(ch["Public"]["by_hour"])==pub_spam,"Public spam shows in its time-of-day chart")
check(sum(ch["#trailchat"]["by_hour"])==0,"no spam on #trailchat")
check(mt["channels_since"] is not None,"channels_since set")
# old history with no channel split still works and is not counted per channel
g.hist[str(int(time.time())//3600*3600-5*86400)]={"m":9,"c":2,"x":0,"g":0,"a":0.0,"h":{}}
mt=g.metrics()
check(sum(r["c"] for r in mt["daily"])>sum(sum(r["c"] for r in c["daily"]) for c in mt["channels"].values()),"old hours count in All only")
# a restart replays nothing twice
before={k:dict(v.get("ch",{})) for k,v in g.hist.items()}
g.hist_mark=time.time(); g._count(g.events[-1])
check({k:dict(v.get("ch",{})) for k,v in g.hist.items()}==before,"no double count after the mark")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
