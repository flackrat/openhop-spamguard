# Keyboard-symbol junk on Public: a standing block (on by default) that holds Public messages containing
# { } ` ^ or \ unless the sender is known. It works on the first message from a new name. Checked against
# openHop's own rule engine. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
class P:
    def __init__(s, key, text, sender):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,key))); s.transport_codes=[0,0]
    def get_path_hashes_hex(s): return ["4C"]
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m, text, sender="Pat Moss", key=None, local=False):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(key or sg.PUBLIC_CHANNEL_KEY,text,sender),
        {"payload_type":5,"hop_count":1,"route_type":1,"local_transmission":local}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
def junk_rules(m): return [r for r in m.policy["policy_engine"]["rules"] if "junk:symbols" in r["name"]]
SOUP=["CT[36%X+{/%!R","YF^;ri}12`Rnue/","m{\\F^yG,tzuJA_BHb^D-FK$Xv",".hC*6JrB`M9SEz"]

# 1. On by default, a standing block limited to Public
check(sg.DEFAULT_CONFIG["symbol_junk"] is True,"on by default")
m=mock(); g=guard(m, floodguard=False)
for i in range(4): m.add("Ann Hill",f"Morning all, day {i}",["4C"],ago=3000-i*60)
g.apply_settings({"mode":"protect"}); sync(g)
b=g.blocks.get("junk:symbols")
check(b is not None and b["kind"]=="links" and b["source"]=="junk" and b.get("only_channel")=="Public","standing block made, Public only")
check(b and b["expires"]-time.time()>sg.PERMANENT_SECONDS/2,"it does not expire")
rs=junk_rules(m)
check(len(rs)==10 and all(r["then"]["action"]=="drop" for r in rs),"ten rules (five text symbols, five name symbols), dropping in Protect")
names=[r["name"] for r in m.policy["policy_engine"]["rules"]]
kn=next((i for i,n in enumerate(names) if "known-people" in n),None)
check(kn is not None and all(names.index(r["name"])>kn for r in rs),"the rules sit after the known-people rule")

# 2. What openHop does with them
check(all(act(m,t)=="drop" for t in SOUP),"symbol junk from a new name is dropped on the first message")
check(g.is_known("Ann Hill") and act(m,"a { b } ^ c","Ann Hill")=="allow","a known name is passed on")
check(act(m,"Morning all, lovely clear skies")=="allow","ordinary chat from a new name is passed on")
check(all(act(m,"Communication broke down, classic",n)=="drop" for n in ("J,YSY*%Z","$OY685UKL","AB<CD>EF","X:Y:Z","P;Q")),
      "an ordinary-looking message from a keyboard-mashed name is dropped on the first message")
check(all(act(m,"Morning all",n)=="allow" for n in ("Mark~G6BNB/R","Dave M3MHA (Thurrock)","GROC#2","John's T-deck","Bingo | Chris")),
      "new names with symbols real people use are passed on")
check(act(m,"Morning","Ann Hill")=="allow","a known name is passed on (name rules too)")
check(act(m,"@[Sam] Rx5 | 9 hops | 4E>B7>9C","Bot 2")=="allow","route replies with | are passed on")
check(act(m,"CT[36%X+{/%!R",key=sg.hashtag_secret("#test"))=="allow","other channels are never touched")
check(act(m,"CT[36%X+{/%!R",local=True)=="allow","this repeater's own companion is never stopped")

# 3. SpamGuard's own records agree (what the page and the evidence log show)
m.add("J,YSY*%Z","YF^;ri}12`Rnue/",["9A","4C"],ago=0); sync(g)
e=next(x for x in g.events if x.sender=="J,YSY*%Z")
check(e.matched=="junk:symbols","the junk message is recorded as caught by the junk block")
m.add("Ann Hill","code is {x}",["4C"],ago=0); sync(g)
e=next(x for x in g.events if x.sender=="Ann Hill" and "{x}" in x.text)
check(e.matched!="junk:symbols","the known name's message is not recorded as caught")
check("symbol junk" in g.describe(b) and g.Q_REASON["junk"],"described in plain words")

# 4. Monitor only logs
g.apply_settings({"mode":"monitor"}); sync(g)
check(act(m,SOUP[0])=="log_only","Monitor: logged, not dropped")

# 5. Removed by hand: not made again for a day
g.apply_settings({"mode":"protect"}); sync(g)
g.action("unblock",{"key":"junk:symbols"}); g.decide(); sync(g)
check("junk:symbols" not in g.blocks and not junk_rules(m),"removed by hand stays removed")
g.suppressed.pop("junk:symbols",None); g.decide(); sync(g)
check("junk:symbols" in g.blocks,"comes back once the day is up")

# 6. Switched off: block and rules go
g.apply_settings({"symbol_junk":False}); g.decide(); sync(g)
check("junk:symbols" not in g.blocks and not junk_rules(m),"off: block and rules gone")
check(act(m,SOUP[0])=="allow","off: passed on")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
