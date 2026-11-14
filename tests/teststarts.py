# Repeater and route blocks that hold only messages STARTING there, checked against openHop's own rule engine.
# All names, messages and repeater codes are made up.
import sys, logging, random
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PUB=sg.PUBLIC_CHANNEL_KEY
class P:
    def __init__(s,path,sender="New Name",text="hello there"):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,PUB))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m,path,sender="New Name"):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(path,sender),{"payload_type":5,"hop_count":len(path),
        "route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
check(sg.DEFAULT_CONFIG["hop_match_mode"]=="starts_known","starting there is the default way to block a repeater")
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"})
g.action("block_hop",{"hop":"E5"}); sync(g)
b=next(x for x in g.blocks.values() if x["kind"]=="hop")
check(g.hop_mode(b)=="starts_known" and "starting at" in g.describe(b),"a repeater block: "+g.describe(b))
check(act(m,["E5"])=="drop" and act(m,["E5","2D","9B"])=="drop","messages that start there are held")
check(act(m,["2D","E5","9B"])=="allow" and act(m,["2D","9B","E5"])=="allow","messages that only pass through it get through")
check(act(m,["E4","E5"])=="allow" and act(m,["E6"])=="allow" and act(m,[])=="allow","neighbouring codes and direct messages are untouched")
check(act(m,["e5","2D"])=="drop","whatever the letter case")
ev=lambda p: sg.Event(ts=0,sender="New Name",text="hello there",path=p,channel="Public")
for p in (["E5"],["E5","2D"],["2D","E5"],["E4"],["E6","E5"]):
    check(g.block_matches(b,ev(p))==(act(m,p)=="drop"),"SpamGuard's own count agrees for "+">".join(p))
# The top code has no code above it
g.action("block_hop",{"hop":"FF"}); sync(g)
check(act(m,["FF","01"])=="drop" and act(m,["FE","FF"])=="allow" and act(m,["01","FF"])=="allow","the last code works too")
# The older choice still works when picked
g.action("block_hop",{"hop":"A1","match":"contains_known"}); sync(g)
check(act(m,["2D","A1"])=="drop","'passing through' still holds anything through it")
# A route block is the start of the route, in order
g.action("block_route",{"route":"C3>D4"}); sync(g)
rb=next(x for x in g.blocks.values() if x["kind"]=="route")
check(act(m,["C3","D4"])=="drop" and act(m,["C3","D4","9B"])=="drop","a route block holds routes starting that way")
check(act(m,["D4","C3"])=="allow" and act(m,["9B","C3","D4"])=="allow" and act(m,["C3","9B","D4"])=="allow","not the same repeaters in another order or place")
check(act(m,["C3","D5"])=="allow" and act(m,["C3"])=="allow","nor a neighbouring code, nor a shorter route")
for p in (["C3","D4"],["C3","D4","01"],["D4","C3"],["01","C3","D4"],["C3"],["C3","D3"],["C3","D5","D4"]):
    check(g.block_matches(rb,ev(p))==(act(m,p)=="drop"),"SpamGuard's own count agrees for route "+">".join(p))
g.action("block_route",{"route":"B7>FF"}); sync(g)
check(act(m,["B7","FF","01"])=="drop" and act(m,["B8","00"])=="allow" and act(m,["B7","FE"])=="allow","a route ending in the top code works too")
# People SpamGuard knows are let through first
g.action("allow_sender",{"sender":"Ann Hill"}); sync(g)
check(act(m,["E5","2D"],"Ann Hill")=="allow","someone you trust still gets through from there")
# Random routes: SpamGuard and openHop always agree
random.seed(5); codes=["E5","E4","E6","C3","D4","FF","A1","01","2D"]; bad=0
m2=mock(); g2=guard(m2,floodguard=False); g2.apply_settings({"mode":"protect"})
g2.action("block_hop",{"hop":"E5"}); g2.action("block_hop",{"hop":"FF"}); g2.action("block_route",{"route":"C3>D4"}); g2.action("block_route",{"route":"A1>FF"}); sync(g2)
bl=[x for x in g2.blocks.values() if x["kind"] in ("hop","route")]
for i in range(300):
    p=[random.choice(codes) for _ in range(random.randint(0,6))]
    if any(g2.block_matches(x,ev(p)) for x in bl)!=(act(m2,p)=="drop"): bad+=1
check(bad==0,f"300 random routes: SpamGuard and openHop agree ({bad} differ)")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
