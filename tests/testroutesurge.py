# Route surge: lots of brand-new names starting on the same first two repeaters within half an hour is
# suggested as a route block (or applied, if the operator allowed that). The protection level scales how
# many names it takes. People SpamGuard knows never count and always get through. All names are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def setup(n, level=50, **over):
    m=mock(); g=guard(m, known_min_msgs=3, **over); g.apply_settings({"mode":"protect","level":level})
    for i,t in enumerate(["Morning all","Nice and clear","Anyone about"]):
        m.add("Quarry Pete",t,["BA","AA","DE"],ago=3000-i*60)   # a regular, on that very route
    for i in range(n):
        m.add(f"Visitor{i:02d}",f"Hello from {i}",["BA","AA","DE"],ago=1500-i*50)
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
    return m,g

P=sg.PRESETS
check([sg.level_values(x)["route_surge_names"] for x in (0,50,100)]==[12,8,5], "the level scales how many new names it takes (12, 8, 5)")
check(sg.META_BY_KEY["route_surge_names"].get("preset") and sg.META_BY_KEY["route_surge_ttl"].get("preset"), "both are starred as set by the level")
check(sg.level_values(0)["route_surge_ttl"]<sg.level_values(50)["route_surge_ttl"]<sg.level_values(100)["route_surge_ttl"], "tougher also lasts longer")
check(sg.DEFAULT_CONFIG["route_auto"] is False and sg.DEFAULT_CONFIG["route_surge"] is True, "suggest on, automatic off by default")

m,g=setup(7)
check(not g.route_suggest, "7 new names is under the balanced limit of 8")
m,g=setup(8)
check("route:BA>AA" in g.route_suggest and g.route_suggest["route:BA>AA"]["names"]==8, f"8 new names on one route is suggested: {g.route_suggest}")
check("route:BA>AA" not in g.blocks, "a suggestion blocks nothing by itself")
check(m.decide("Visitor99","Hi",["BA","AA","DE"])=="allow", "so a message still goes through")
st=g.status()
check(st["route_suggestions"] and st["route_suggestions"][0]["route"]=="BA>AA" and st["route_suggestions"][0]["ttl"]==7200, "shown on the page with how long it would last")

m,g=setup(10, level=0)
check(not g.route_suggest, "Gentle waits for 12")
m,g=setup(5, level=100)
check("route:BA>AA" in g.route_suggest, "Tough suggests from 5")

m,g=setup(8)
g.action("accept_route",{"route":"BA>AA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
b=g.blocks.get("route:BA>AA")
check(b and b["kind"]=="route" and b["source"]=="manual" and 7000<b["expires"]-b["created"]<=7200, "accepting blocks it for the level's time")
check("route:BA>AA" not in g.route_suggest and not g.status()["route_suggestions"], "and clears the suggestion")
check(m.decide("Visitor99","Hi",["BA","AA","DE"])=="drop", "a newcomer on the route is held")
check(m.decide("Quarry Pete","Back again",["BA","AA","DE"])=="allow", "a known regular on the same route still gets through")
check(m.decide("Canal Boat Ted","Out on the lock",["BA","B1","DE"])=="allow", "the same first repeater on another route is untouched")

m,g=setup(8)
g.action("dismiss_route",{"route":"BA>AA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.route_suggest and "route:BA>AA" not in g.blocks, "dismissing removes it and blocks nothing")
check(g.suppressed.get("route:BA>AA",0)>time.time()+80000, "and it stays quiet for a day")

m,g=setup(8, route_auto=True)
b=g.blocks.get("route:BA>AA")
check(b and b["source"]=="route-auto" and not g.route_suggest, "automatic mode applies it without asking")
check(m.decide("Visitor99","Hi",["BA","AA","DE"])=="drop" and m.decide("Quarry Pete","Back",["BA","AA","DE"])=="allow", "and still lets known people through")
check("route:BA>AA" in [x["key"] for x in g.status()["blocks"]], "it is listed with the other blocks")

# at most three automatic blocks at once
m=mock(); g=guard(m, known_min_msgs=3, route_auto=True); g.apply_settings({"mode":"protect"})
for r in range(5):
    for i in range(8): m.add(f"V{r}x{i}",f"Hi {i}",[f"A{r}","CC","DE"],ago=1500-i*50)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
n=sum(1 for b in g.blocks.values() if b.get("source")=="route-auto")
check(n==sg.ROUTE_AUTO_MAX and len(g.route_suggest)==5-n, f"no more than {sg.ROUTE_AUTO_MAX} automatic blocks, the rest are suggestions ({n}, {len(g.route_suggest)})")

# known people, and blocked or allowed repeaters, never count
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(10):
    for k in range(3): m.add(f"Regular{i}",f"Chat {k}",["BA","AA","DE"],ago=1700-i*60-k*5)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.route_suggest, "ten regulars chatting on one route is a conversation, not a surge")
m,g=setup(8); g.route_suggest.clear(); g.action("block_hop",{"hop":"BA"}); g.decide()
check("route:BA>AA" not in g.route_suggest, "no suggestion when the first repeater is already blocked")
m,g=setup(8, route_surge=False)
check(not g.route_suggest, "turned off, nothing is suggested")
m,g=setup(8, allow_hops=["BA"])
check(not g.route_suggest, "nothing for a repeater you allowed")

# only names, routes and timing: message text makes no difference
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(8): m.add(f"Visitor{i:02d}","The very same words every time",["BA","AA","DE"],ago=1500-i*50)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
a=set(g.route_suggest)
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(8): m.add(f"Visitor{i:02d}",f"Completely different thing number {i} about {i*7}",["BA","AA","DE"],ago=1500-i*50)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(a==set(g.route_suggest) and a, "same result whatever the messages say")
# Quick bursts: the repeater-wide check used to block all of BA; when the new names nearly all share one route,
# only that route is blocked and a newcomer using the same first repeater another way gets through.
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all","Nice and clear","Anyone about"]): m.add("Quarry Pete",t,["BA","AA","DE"],ago=3000-i*60)
for i,n in enumerate(["Dave","Sarah","Mike","Emma","Paul","Kate","Rob"]): m.add(n,["Lovely day on the hill","Anyone got a spare lead","Traffic is awful near the bridge","Fresh bread at the bakery","Match starts at three","Heading to the market now","Rain coming in from the west"][i],["BA","AA","DE"],ago=400-i*30)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
b=g.blocks.get("route:BA>AA")
check(b and b["source"]=="hop-route" and "hop:BA" not in g.blocks, f"a quick burst on one route blocks the route, not the repeater: {list(g.blocks)}")
check(m.decide("Lucy","Hi",["BA","AA","DE"])=="drop", "a newcomer on that route is held")
check(m.decide("Canal Boat Ted","Out on the lock",["BA","DE","B1"])=="allow", "a newcomer using the same first repeater another way gets through")
check(m.decide("Quarry Pete","Back again",["BA","AA","DE"])=="allow", "a known regular on the route gets through")
st=g.status(); check(any(x["key"]=="route:BA>AA" and x["source"]=="hop-route" for x in st["blocks"]), "it is listed as an automatic route block")

# made-up names are stronger evidence: the whole repeater is still blocked
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(6): m.add(rname(),f"Free thing {i}",["BA","AA","DE"],ago=300-i*20)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check("hop:BA" in g.blocks and "route:BA>AA" not in g.blocks, f"made-up names still block the repeater: {list(g.blocks)}")

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
