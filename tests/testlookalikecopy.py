# With the copied-name check on: a near-identical spelling of a nearby person's name is treated as the same
# person, a copy arriving from far away through a repeater they never use is held, and
# those messages don't rewrite who the person is, so the copy can't switch the check off by flooding. A hold
# that keeps catching copies stays on. All names and messages are made up.
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
FAR=["F1","82","A6","5D","C1","3C","79","26","07"]
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]

m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(8): m.add("Sam Lowmesh",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"] if i%3 else ["07","3B"],ago=6600-i*700)
g.apply_settings({"mode":"protect"}); sync(g)
check(g._local("Sam Lowmesh"),"Sam is a nearby regular")
check(g.name_family("Sam Lowmack")==g.name_family("Sam-Lowmesh"),"a near-identical spelling joins the family")
check(g._local("Sam Lowmack"),"so it inherits the family's history")
check(g.name_family("Sam Lowmesh")!=g.name_family("Bob Stone"),"unrelated names stay apart")

# the first copy is held, and a flood of copies under other spellings doesn't teach SpamGuard a new way in
m.add("Sam Lowmack","hello",FAR,ago=0); sync(g)
check(any(b["kind"]=="imposter" and b["value"]=="F1" for b in g.blocks.values()),"copy held from that repeater")
for i in range(6): m.add(["Sam Lowmack","Sam-Lowmesh","SamLowmesh"][i%3],f"{words[i]} {i} nonsense",FAR[:8+i%2]+["07"],ago=0)
sync(g)
check("F1" not in g._family_homes("Sam Lowmesh"),"never learnt as a way in")
check(g._usual_hops("Sam Lowmesh") is not None and g._usual_hops("Sam Lowmesh")<=g.LOCAL_HOPS,"usual distance unchanged")
check(g._local("Sam Lowmesh"),"still recognised as nearby after the flood")
check(act(m,"another one","Sam Lowmack",FAR)=="drop","the same spelling is dropped from there")
check(any(b["kind"]=="imposter" and b.get("who")=="Sam-Lowmesh" and b["value"]=="F1" for b in g.blocks.values()),"each new spelling is held on its first copy")
check(act(m,"another one","Sam-Lowmesh",FAR)=="drop","and dropped from then on")
check(act(m,"evening all","Sam Lowmesh",["07"])=="allow","the real person from the usual way in gets through")
check(act(m,"evening all","Sam Lowmack",["07"])=="allow","and so does a spelling from the usual way in")
check(act(m,"evening all","Sam Lowmesh",["5B","07"])=="allow","and from somewhere else nearby")
check(act(m,"hello","Bob Stone",FAR)=="allow","an unrelated name from there is not held by this")

# a hold that keeps catching copies stays on
b=next(b for b in g.blocks.values() if b.get("source")=="spoof" and b["value"]=="F1")
b["expires"]=time.time()+60
m.add("Sam-Lowmesh","still here",FAR,ago=0); sync(g)
check(b["expires"]>time.time()+3000,"kept on while it is still catching copies")
check(b["expires"]<=b["created"]+86400+1,"but never more than a day from when it started")

# after a restart the saved history is where a lookalike joins, whichever spelling is heard first
m4=mock(); g4=guard(m4,floodguard=False,spoof_watch=True)
g4.near["samlowmesh"]=[1,1,2,1,1,2]
check(g4.name_family("Sam Lowmack")=="samlowmesh","a lookalike heard first still joins the saved family")
check(g4.name_family("Sam Lowmesh")=="samlowmesh","and the saved spelling keeps its key")

# off (the default): names are not merged and nothing is held
m3=mock(); g3=guard(m3,floodguard=False,known_min_msgs=3,known_min_minutes=60)
check(g3.name_family("Sam Lowmack")!=g3.name_family("Sam Lowmesh"),"off: spellings stay apart")
for i in range(8): m3.add("Sam Lowmesh",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"],ago=6600-i*700)
g3.apply_settings({"mode":"protect"}); sync(g3)
m3.add("Sam Lowmack","hello",FAR,ago=0); sync(g3)
check(not any(b.get("source")=="spoof" for b in g3.blocks.values()),"off: nothing held as spoofed")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
