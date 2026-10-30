# Audit: with common settings (protect mode, known people, manual text / hop / route blocks), every figure that
# reports spam agrees: the Overview tiles, the hourly and daily graphs, the per-channel split and the spam map's data.
# Blocks you add yourself count as spam stopped, never as "possibly genuine held". All names are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all from the hill","Nice and clear today"]):
    m.add("Quarry Pete",t,["9D","4C","2F"],ago=900-i*60)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
g.action("block_text",{"text":"FREE PRIZE claim your gift now","channel":"Public"})
g.action("block_hop",{"hop":"7E"})
g.action("block_route",{"route":"9D>4C"})
g.last_sync=0; g.sync_pending=True; g.poll_once()
now=time.time()
for b in g.blocks.values(): b["created"]=now-2000
m.add("Canal Boat Ted","Anyone out on the lock this morning?",["7E","B1"],ago=330)   # via a blocked repeater
m.add("Reed Warbler","Good evening all",["9D","4C","2F"],ago=320)                    # via a blocked route
m.add("UD6DWREK","FREE PRIZE claim your gift now",["B1","2F"],ago=310)                  # blocked text
m.add("Hill Walker","FREE PRIZE claim your gift now",["B1","2F"],ago=300)               # blocked text
m.add("Quarry Pete","Lovely morning on the quarry road",["9D","4C","2F"],ago=290)       # known person on a blocked route
g.poll_once()
met=g.status()["metrics"]
d1,d7=met["d1"],met["d7"]
check(d1["c"]==4 and d1["g"]==0, f"all 4 manual-block catches count as stopped, none as held: {d1}")
check(d1["x"]==0, "nothing let through")
check(d7["c"]==d1["c"], "7 day tile agrees with the 24 hour tile")
check(sum(r["c"] for r in met["hourly"])==d1["c"], "hourly graph sums to the tile")
check(sum(r["x"] for r in met["hourly"])==d1["x"], "hourly let-through sums to the tile")
check(sum(r["m"] for r in met["hourly"])==d1["m"], "hourly messages sum to the tile")
check(sum(r["c"] for r in met["daily"])==d7["c"], "daily graph sums to the 7 day tile")
check(sum(met["by_hour"])==d7["c"]+d7["x"], "by-hour graph sums to the spam total")
pc=met["channels"].get("Public")
check(bool(pc) and pc["d1"]["c"]==d1["c"], f"per-channel split agrees: {pc and pc['d1']}")
check(pc and sum(r["c"] for r in pc["hourly"])==d1["c"], "per-channel hourly agrees")
check(sum(s["d7"] for s in met["sources"])==d7["c"]+d7["x"], "first-hop table sums to the spam total")
routed=sum(n for v in g.hist.values() for n in (v.get("p") or {}).values())
check(routed==d7["c"]+d7["x"], f"map routes cover every spam message with a route: {routed}")
check(met["unplaced"]["d7"]<=d7["c"]+d7["x"], "map unplaced never exceeds spam")
check(sum(e["d7"] for e in met["entries"])+met["unplaced"]["d7"]<=d7["c"]+d7["x"], "map entries plus unplaced never exceed spam")

# --- the tiles use the same windows as the graphs, including at the edges
th=int(time.time()//3600*3600)
g.hist[str(th-24*3600)]={"m":5,"c":5,"x":0,"g":0,"a":0.0,"h":{"B1":5}}      # just outside the 24 hourly columns
g.hist[str(th-23*3600)]={"m":3,"c":2,"x":1,"g":0,"a":0.0,"h":{"B1":3}}      # the oldest column shown
d0=int(time.mktime(time.localtime()[:3]+(0,0,0,0,0,-1)))
g.hist[str(d0-7*86400+3600)]={"m":4,"c":4,"x":0,"g":0,"a":0.0,"h":{"B1":4}} # older than the 7 calendar days
met=g.status()["metrics"]
check(met["d1"]["c"]==sum(r["c"] for r in met["hourly"]) and met["d1"]["x"]==sum(r["x"] for r in met["hourly"]),
      f"24 h tile equals the hourly graph: {met['d1']['c']}/{met['d1']['x']}")
check(met["d7"]["c"]==sum(r["c"] for r in met["daily"]) and met["d7"]["x"]==sum(r["x"] for r in met["daily"]),
      f"7 day tile equals the daily graph: {met['d7']['c']}")
check(sum(met["by_hour"])==met["d7"]["c"]+met["d7"]["x"], "by-hour graph still equals the 7 day spam total")
check(sum(s["d7"] for s in met["sources"])==met["d7"]["c"]+met["d7"]["x"], "first-hop table equals the 7 day spam total")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
