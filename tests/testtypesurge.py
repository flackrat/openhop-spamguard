# Type surge: a flood of requests, anonymous requests or group data (encrypted, not channel text) coming through
# one first repeater is suggested as a hold on that kind of packet from that repeater, or applied if the operator
# allowed that. Only counts, routes and timing are used. Channel text and direct packets are never touched.
# All codes are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def pkt(m, ptype, path, ago, route=1, rssi=-95, snr=4):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":ptype,"route":route,"rssi":rssi,"snr":snr,
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path),"transmitted":True,"drop_reason":None})

def setup(n, ptype=6, hop="BA", level=50, others=0, **over):
    m=mock(); g=guard(m, known_min_msgs=3, **over); g.apply_settings({"mode":"protect","level":level})
    for i in range(n): pkt(m, ptype, [hop,"AA"], ago=500-i*(400/max(n,1)))
    for i in range(others): pkt(m, ptype, ["CC","AA"], ago=450-i*(400/max(others,1)))
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
    return m,g

def ev(m, ptype, route, path):
    class P:
        def __init__(s): s.payload=bytearray(b"\x00"*20); s.transport_codes=[0,0]
        def get_path_hashes_hex(s): return path
        def get_payload_type(s): return ptype
        def get_payload(s): return s.payload
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(),{"payload_type":ptype,"route_type":route,"hop_count":len(path)}).action

check([sg.level_values(x)["type_surge_packets"] for x in (0,50,100)]==[60,40,25], "the level scales how many packets it takes (60, 40, 25)")
check(sg.META_BY_KEY["type_surge_packets"].get("preset"), "starred as set by the level")
check(sg.DEFAULT_CONFIG["type_auto"] is False and sg.DEFAULT_CONFIG["type_surge"] is True, "suggest on, automatic off by default")

m,g=setup(39)
check(not g.type_suggest, "39 is under the balanced limit of 40")
m,g=setup(40)
s=g.type_suggest.get("ptype:6:BA")
check(s and s["packets"]==40 and s["share"]==100 and s["label"]=="group data", f"40 group data packets through one repeater is suggested: {g.type_suggest}")
check("ptype:6:BA" not in g.blocks and ev(m,6,1,["BA","AA"])=="allow", "a suggestion holds nothing by itself")
ts=g.status()["type_suggestions"]
check(ts and ts[0]["hop"]=="BA" and ts[0]["ttl"]==7200 and ts[0]["minutes"]==10, "shown on the page with how long a hold lasts")
m,g=setup(50, level=0)
check(not g.type_suggest, "Gentle waits for 60")
m,g=setup(25, level=100)
check("ptype:6:BA" in g.type_suggest, "Tough suggests from 25")
for pt,name in ((0,"requests"),(7,"anonymous requests")):
    m,g=setup(40, ptype=pt)
    check(f"ptype:{pt}:BA" in g.type_suggest and g.type_suggest[f"ptype:{pt}:BA"]["label"]==name, f"{name} are watched too")
m,g=setup(40, ptype=4)
check(not g.type_suggest, "adverts and other kinds are not part of this")
m,g=setup(40, ptype=5)
check(not g.type_suggest, "channel text is never part of this")
m,g=setup(40, others=40)
check(not g.type_suggest, "two repeaters sharing the flood equally: nothing stands out")

m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(40): pkt(m,6,["BA","AA"],ago=500-i*9,route=2)        # direct (routed)
for i in range(40): pkt(m,6,["BA","AA"],ago=500-i*9,rssi=0,snr=0)         # sent by this repeater itself
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.type_suggest, "direct packets and this repeater's own never count")

m,g=setup(40)
g.action("accept_type",{"ptype":6,"hop":"BA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
b=g.blocks.get("ptype:6:BA")
check(b and b["kind"]=="ptype" and b["source"]=="manual" and 7000<b["expires"]-b["created"]<=7200 and not g.type_suggest, "accepting holds it for the level's time and clears the suggestion")
check(ev(m,6,1,["BA","AA"])=="drop" and ev(m,6,0,["BA","AA"])=="drop", "flooded group data through that repeater is held")
check(ev(m,6,1,["CC","AA"])=="allow", "the same kind through another repeater is untouched")
check(ev(m,6,2,["BA","AA"])=="allow", "a direct packet through it is untouched")
check(ev(m,5,1,["BA","AA"])=="allow", "channel text through it is untouched")
check(ev(m,0,1,["BA","AA"])=="allow", "another kind through it is untouched")
check("flooded group data" in g.describe(b) and any(x["kind"]=="ptype" for x in g.status()["blocks"]), "described in plain words and listed with the other blocks")
check(g.rule_numbers(b), "its openHop rule number is shown")
g.action("unblock",{"key":"ptype:6:BA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(ev(m,6,1,["BA","AA"])=="allow", "removing it lets them through again")

m,g=setup(40)
g.action("dismiss_type",{"ptype":6,"hop":"BA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.type_suggest and "ptype:6:BA" not in g.blocks and g.suppressed.get("ptype:6:BA",0)>time.time()+80000, "dismissing blocks nothing and stays quiet for a day")

m,g=setup(40, type_auto=True)
b=g.blocks.get("ptype:6:BA")
check(b and b["source"]=="type-auto" and not g.type_suggest and ev(m,6,1,["BA","AA"])=="drop", "automatic mode applies it without asking")

m=mock(); g=guard(m, known_min_msgs=3, type_auto=True); g.apply_settings({"mode":"protect"})
for r,h in enumerate(["B1","B2","B3","B4","B5"]):
    for i in range(40): pkt(m,6,[h,"AA"],ago=500-i*9)
    for i in range(40): pkt(m,7,[h,"AA"],ago=500-i*9)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
n=sum(1 for b in g.blocks.values() if b.get("source")=="type-auto")
check(n<=sg.TYPE_AUTO_MAX, f"at most {sg.TYPE_AUTO_MAX} automatic holds at once ({n})")

m,g=setup(40, type_surge=False)
check(not g.type_suggest, "turned off, nothing is suggested")
m,g=setup(40, allow_hops=["BA"])
check(not g.type_suggest, "nothing for a repeater you allowed")

m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"monitor"})
for i in range(40): pkt(m,6,["BA","AA"],ago=500-i*9)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
g.action("accept_type",{"ptype":6,"hop":"BA"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(ev(m,6,1,["BA","AA"])!="drop", "in Monitor mode an accepted hold only watches")
try: g.action("accept_type",{"ptype":4,"hop":"BA"}); check(False,"an unwatched kind is refused")
except ValueError: check(True,"")
# a slow, steady flood: too few in ten minutes, but enough over two hours
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(22): pkt(m,6,["BA","AA"],ago=6800-i*300)
for i in range(3): pkt(m,6,["CC","AA"],ago=6000-i*900)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
s=g.type_suggest.get("ptype:6:BA")
check(s and s["minutes"]==120 and s["packets"]==22, f"a slow flood over two hours is suggested too: {g.type_suggest}")
check(g.status()["type_suggestions"][0]["minutes"]==120, "and the page says two hours")
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(15): pkt(m,6,["BA","AA"],ago=6800-i*300)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.type_suggest, "15 in two hours is under the limit of 20")
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(14): pkt(m,6,["BA","AA"],ago=6800-i*300)
for i in range(14): pkt(m,6,["CC","AA"],ago=6700-i*300)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.type_suggest, "two repeaters sharing a slow flood equally: nothing stands out")
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i in range(25): pkt(m,6,["BA","AA"],ago=3000-i*10)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not g.type_suggest, "a short burst that is too small for ten minutes is not a slow flood")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
