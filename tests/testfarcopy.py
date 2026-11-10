# 6.31.1: a name nearly always heard a few hops away, suddenly arriving from far off through a repeater it is
# never heard through, is someone copying it: held from that repeater, whatever the text and whether or not an
# attack is under way, and those messages don't teach SpamGuard a new way in. All names and messages are made up.
import sys, logging, json
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

m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(8): m.add("Ann Hill",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"] if i%3 else ["07","3B"],ago=6600-i*700)
for i in range(8): m.add("Bob Far",f"{words[i]} {words[(i*5)%11]} news {i}",["9C","1A","2B","3C","4D","5E","6F","70","81","92"],ago=6500-i*700)
g.apply_settings({"mode":"protect"}); sync(g)
check(g._local("Ann Hill") and not g._local("Bob Far"),"Ann is local, Bob is usually far")
check(not g.attack_on(time.time()),"no attack under way")

# a plain message under Ann's name from far away, through a repeater she never uses
m.add("Ann Hill","hello",FAR,ago=0); sync(g)
check(any(b["kind"]=="imposter" and b["value"]=="F1" and b.get("who")=="Ann Hill" for b in g.blocks.values()),
      "held from that repeater even though the text is ordinary")
check("F1" not in g.homes.get("Ann Hill",{}) and 9 not in g.near.get("Ann Hill",[]),"not learnt as a way in")
check(act(m,"you lot are idiots","Ann Hill",FAR)=="drop","the next copy from there is dropped")
check(act(m,"evening all","Ann Hill",["07"])=="allow","the real Ann from her usual way in gets through")
check(act(m,"evening all","Ann Hill",["5B","07"])=="allow","and from somewhere else nearby")

# someone usually far away turning up through a new repeater: left alone
m.add("Bob Far","hello from the hills",["AA","1A","2B","3C","4D","5E","6F","70","81"],ago=0); sync(g)
check(not any(b["kind"]=="imposter" and b.get("who")=="Bob Far" for b in g.blocks.values()),"a far-off regular is left alone")

# the hop history is saved and loaded, rejecting bad values
g._save_state(force=True)
path=g.file_cfg.get("state_file", sg.DEFAULT_CONFIG["state_file"])
st=json.load(open(path)); check(st.get("near",{}).get("Ann Hill")==g.near["Ann Hill"],"saved")
st["near"]={"Ann Hill":[1,2,"x",99,-1,True,3]}; json.dump(st,open(path,"w"))
g.near.clear(); g._load_state()
check(g.near.get("Ann Hill")==[1,2,3],"bad hop counts rejected on load")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
