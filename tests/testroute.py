# Blocking a route: spam that always starts on the same first repeaters (here 9D then 4C) can be held without
# blocking everyone who uses the first repeater. People SpamGuard knows still get through, and it is checked
# against openHop's real rule engine. All names, messages and codes are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

check(sg.parse_route("9d>4c")==["9D","4C"] and sg.parse_route("0x9D, 0x4C")==["9D","4C"] and sg.parse_route("9D 4C 2F")==["9D","4C","2F"], "routes can be typed as 9D>4C, with spaces or commas")
for bad in ["9D", "9D>4C>2F>B1>7E", "9D>ZZ", "9D>4C11"]:
    try: sg.parse_route(bad); check(False, f"refused: {bad}")
    except ValueError: check(True, "")

m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all from the hill","Nice and clear today"]):
    m.add("Quarry Pete",t,["9D","4C","2F"],ago=600-i*60)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Quarry Pete"), "a regular on that route is known")

r=g.action("block_route",{"route":"9D>4C"})
check("route:9D>4C" in g.blocks and "route 9D>4C" in r.get("message","").replace("on route","route"), f"the route block is added: {r}")
b=g.blocks["route:9D>4C"]
check(b["kind"]=="route" and b["value"]==["9D","4C"] and b["source"]=="manual", "as a block you added")
g.last_sync=0; g.sync_pending=True; g.poll_once()

check(m.decide("UD6DWREK","FREE PRIZE claim now",["9D","4C","2F"])=="drop", "spam starting 9D>4C is held by openHop")
check(m.decide("Canal Boat Ted","Anyone out on the lock?",["9D","B1","2F"])=="allow", "someone else whose message starts at 9D but goes another way gets through")
check(m.decide("Canal Boat Ted","Morning",["B1","2F"])=="allow", "and other routes are untouched")
check(m.decide("Quarry Pete","Back again",["9D","4C","2F"])=="allow", "a known person on the blocked route still gets through")

# SpamGuard's own records check the order exactly
E=sg.Event
e1=E(ts=0,sender="X",text="t",path=["9D","4C","2F"],channel="Public")
e2=E(ts=0,sender="X",text="t",path=["2F","4C","9D"],channel="Public")
e3=E(ts=0,sender="X",text="t",path=["9D"],channel="Public")
check(g.block_matches(b,e1) and not g.block_matches(b,e2) and not g.block_matches(b,e3), "SpamGuard's own records check the route starts that way, in that order")
check("route 9D>4C" in g.describe(b) and "except people it knows" in g.describe(b), f"described in plain words: {g.describe(b)}")
st=g.status()
check(any(x["kind"]=="route" and x["key"]=="route:9D>4C" for x in st["blocks"]), "listed with the other blocks")
check(g.rule_numbers(b), "its openHop rule numbers are shown, like other blocks")

g.action("unblock",{"key":"route:9D>4C"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check("route:9D>4C" not in g.blocks and m.decide("UD6DWREK","FREE PRIZE claim now",["9D","4C","2F"])=="allow", "removing it lets the route through again")

# only on one channel
g.action("block_route",{"route":"9D>4C","channel":"Public"})
check(g.blocks["route:9D>4C"].get("only_channel")=="Public" and "only on Public" in g.describe(g.blocks["route:9D>4C"]), "a route block can be limited to one channel")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
