# Spam marks on known names, and link campaigns. Checked against openHop's own rule engine. All names and messages are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
class P:
    def __init__(s,text,sender,path):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,sg.PUBLIC_CHANNEL_KEY))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m,text,sender,path):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(text,sender,path),{"payload_type":5,"hop_count":len(path),
        "route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
FAST=dict(floodguard=False,known_min_msgs=3,known_min_minutes=60,vary_limits=False)

# A known name that sends spam through its own usual way in: a spam mark ends its known pass
m=mock(); g=guard(m,**FAST)
for i in range(8): m.add("Tom Reed",f"{words[i]} {words[(i*3)%11]} chat {i}",["4C"],ago=6600-i*700)
g.apply_settings({"mode":"protect"}); sync(g)
check(g.is_known("Tom Reed"),"Tom is known")
r=g.action("label",{"label":"spam","sender":"Tom Reed","text":"buy cheap widgets","path":["4C"],"packet":"p1"})
check(not g.is_known("Tom Reed"),"after a spam mark through his usual way in he is no longer known")
check("no longer counts as a known person" in r.get("message",""),"the reply says so")
check("Tom Reed" in g.spam_marked,"and the mark is kept against the name")
check(not any(b.get("who")=="Tom Reed" for b in g.blocks.values()),"no copy hold for him")

# A copy of a known name through a repeater that name never uses: the mark holds the name from there only
m2=mock(); g2=guard(m2,**FAST)
for i in range(8): m2.add("Ann Hill",f"{words[i]} {words[(i*5)%11]} news {i}",["4C"] if i%2 else ["4C","5E"],ago=6600-i*700)
g2.apply_settings({"mode":"protect"}); sync(g2)
r=g2.action("label",{"label":"spam","sender":"Ann Hill","text":"rude copy","path":"E7>9B>2D","packet":"p2"})
b=[b for b in g2.blocks.values() if b["kind"]=="imposter" and b.get("who")=="Ann Hill"]
check(bool(b) and b[0]["value"]=="E7" and b[0]["source"]=="manual","copy held from that repeater")
check("doesn't use" in r.get("message",""),"the reply says it looked like a copy")
check(g2.is_known("Ann Hill") and "Ann Hill" not in g2.spam_marked,"the real person keeps her standing")
sync(g2)
check(act(m2,"another rude copy","Ann Hill",["E7","9B","2D"])=="drop","the copy is dropped there")
check(act(m2,"evening all","Ann Hill",["4C"])=="allow","the real person still gets through")

# Marks on names SpamGuard doesn't know change nothing about known status
r=g2.action("label",{"label":"spam","sender":"Zed Nobody","text":"hello","path":["C3"],"packet":"p3"})
check(not any(b.get("who")=="Zed Nobody" for b in g2.blocks.values()),"unknown name: no hold from a mark")

# Several new names posting short links to one site start a link hold
m3=mock(); g3=guard(m3,**FAST); g3.apply_settings({"mode":"protect"})
for i,n in enumerate(["Kim Lane","Lou Park","Max Dale","Ned Ford","Oli West"]):
    m3.add(n,f"look https://zq.io/{i}x",["A1","B2"] if i%2 else ["C3","D4"],ago=600-i*60); sync(g3)
check(any(b.get("source")=="linkhost" for b in g3.blocks.values()),"short links to one site: link hold")
check(act(m3,"see https://zq.io/zz","Pat Gale",["E5"])=="drop","the next new name's link to it is dropped")
check(sg.link_host("hello there")=="" and sg.link_host("go to http://ab.co/x now")=="ab.co","site read from short links")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
