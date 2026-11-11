# What SpamGuard records as held is what openHop's rules actually hold: for your own blocks of every kind and
# hundreds of random messages, the two agree. Made-up names, messages and repeater codes.
import sys, logging, random
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PUB=sg.PUBLIC_CHANNEL_KEY; TRAIL=sg.hashtag_secret("trailchat")
KEYS={"Public":PUB,"#trailchat":TRAIL}
class P:
    def __init__(s,text,sender,path,key):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,key))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"})
g.action("add_channel",{"name":"#trailchat","key":TRAIL})
g.action("block_route",{"route":"A1>B2"})
g.action("block_route",{"route":"C3>D4","channel":"#trailchat"})
g.action("block_hop",{"hop":"E5","match":"contains"})
g.action("block_text",{"text":"cheap widgets for sale","channel":"*"})
g.action("block_text",{"text":"win a free holiday","channel":"#trailchat"})
g.action("mute",{"sender":"Zed Quill","channel":"*","days":7})
g.action("mute",{"sender":"Lou Park","channel":"Public","days":7})
g.action("hold_name_hop",{"sender":"Ann Hill","hop":"F6","channel":"#trailchat"})
sync(g)
rnd=random.Random(11)
HOPS=["A1","B2","C3","D4","E5","F6","77","88"]
NAMES=["Zed Quill","Lou Park","Ann Hill","Kim Lane","Max Dale"]
TEXTS=["cheap widgets for sale today","win a free holiday now","morning all","radio check please","anyone on tonight"]
same=diff=0
for i in range(600):
    path=rnd.sample(HOPS,rnd.randint(1,5)); who=rnd.choice(NAMES); text=rnd.choice(TEXTS)+f" {i}"; ch=rnd.choice(list(KEYS))
    oh=PolicyEngine(m.policy["policy_engine"]).evaluate(P(text,who,path,KEYS[ch]),{"payload_type":5,"hop_count":len(path),"route_type":1,"local_transmission":False}).action=="drop"
    e=sg.Event(ts=0,sender=who,text=text,path=path,channel=ch)
    local=any(g.block_matches(b,e) for b in g.blocks.values())
    if oh==local: same+=1
    else:
        diff+=1
        if diff<=5: print("  differs:",who,ch,path,text,"openHop" if oh else "local only")
check(diff==0,f"SpamGuard's record and openHop agree on every message ({same} of {same+diff})")
check(same>0 and any(True for _ in range(1)),"messages were compared")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
