# Senders are read the same way openHop's rules read them, so a rule about a name matches what SpamGuard counted.
# Checked against openHop's own parser and rule engine. All names and messages are made up.
import sys, logging, json, time, os, hmac, hashlib, random
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
KEY=sg.PUBLIC_CHANNEL_KEY
def plain(content,flags=0):
    pt=int(time.time()).to_bytes(4,"little")+bytes([flags])+content
    return pt+b"\x00"*((-len(pt))%16)
def enc_pt(pt):
    k=sg._secret32(KEY); ct=AES.new(k[:16],AES.MODE_ECB).encrypt(pt)
    return bytes([sg.channel_hash_byte(KEY)])+hmac.new(k,ct,hashlib.sha256).digest()[:2]+ct
def add_raw(m,content,path,flags=0):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time(),"type":5,"payload":enc_pt(plain(content,flags)).hex(),
        "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})
class P:
    def __init__(s,payload,path): s.payload=bytearray(payload); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act_raw(m,content,path,flags=0):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(enc_pt(plain(content,flags)),path),{"payload_type":5,
        "hop_count":len(path),"route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
def oh_name(content,flags=0):
    p=PolicyEngine._parse_channel_plaintext(plain(content,flags))
    s,_=PolicyEngine._extract_sender_from_message(p["content"])
    return s.rstrip("\x00").rstrip()

# The sender matches openHop's reading for every shape of name
rnd=random.Random(5)
cases=[b"Ann Hill: hi",b" Ann Hill: hi",b"\tAnn Hill: hi",b"Ann Hill : hi",b"Ann Hill\t: hi",b"no name here",
       b"xxAnn Hill: hi",b"Ann: Hill: hi",b": hi",b"Ann Hill: hi\x00hidden",b"  : hi"]
for _ in range(60):
    name="".join(rnd.choice(" \tAbc-x.") for _ in range(rnd.randint(0,8)))
    cases.append((name+": "+rnd.choice(["hello","x","a: b"])).encode())
same=0
for c in cases:
    for flags in (0,1,2):
        d=sg.decrypt_group_text(enc_pt(plain(c,flags)),{"Public":KEY})
        conds=sg.sender_conds(d["sender"] or "?") if d is not None else []
        if d is not None and all(PolicyEngine._compare(oh_name(c,flags),x["op"],x["value"]) for x in conds): same+=1
        else: print("  differs:",c,flags,d and d["sender"],oh_name(c,flags))
check(same==len(cases)*3,f"every sender read as openHop reads it ({same} of {len(cases)*3})")

FAST=dict(floodguard=False,known_min_msgs=3,known_min_minutes=60,vary_limits=False,quick_resend_hold=True)

# A name with a leading space: its own repeats are stopped in openHop
m=mock(); g=guard(m,**FAST); g.apply_settings({"mode":"protect"})
for i in range(8): add_raw(m,b" Zed Quill: cheap widgets now",["A1","B2"]); sync(g)
check(act_raw(m,b" Zed Quill: cheap widgets now",["A1","B2"])=="drop","leading-space name: repeats dropped")
check(act_raw(m,b"Zed Quill: cheap widgets now",["C3"])=="allow","the plain name is a different sender")

# No name at all: repeats are stopped in openHop too
m2=mock(); g2=guard(m2,**FAST); g2.apply_settings({"mode":"protect"})
for i in range(8): add_raw(m2,b"cheap widgets now",["A1","B2"]); sync(g2)
check(act_raw(m2,b"cheap widgets now",["A1","B2"])=="drop","nameless repeats dropped")

# Flags 0x02: SpamGuard sees the name openHop sees, so repeats under it are stopped
m3=mock(); g3=guard(m3,**FAST); g3.apply_settings({"mode":"protect"})
for i in range(8): add_raw(m3,b"xxCal Moss: cheap widgets now",["A1","B2"],flags=2); sync(g3)
check(any(x.sender=="Cal Moss" for x in g3.events),"flags 0x02: read as the name openHop reads")
check(act_raw(m3,b"xxCal Moss: cheap widgets now",["A1","B2"],flags=2)=="drop","flags 0x02 repeats dropped")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
