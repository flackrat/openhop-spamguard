# 6.31.2: further copied-name experiment cases, and holding a name from one repeater yourself.
# Checked against openHop's own rule engine. All names and messages are made up.
import sys, logging, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def enc_at(sender,text,sent,key=sg.PUBLIC_CHANNEL_KEY):
    return enc(sender,text,key,sent=sent)
def add_at(m,sender,text,path,sent,ago=0):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":5,"payload":enc_at(sender,text,sent),
        "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})
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
OFF=254*86400
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]

m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(6): add_at(m,"Ann Hill",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"],time.time()-(6600-i*700),ago=6600-i*700)
# copies earlier in the day (before the check could tell) made F1 look like one of her ways in
for i in range(6): m.add("Ann Hill",f"copy {words[i]} {i}",["F1","82","A6"],ago=3000-i*100)
g.apply_settings({"mode":"protect"}); sync(g)
check("F1" in g.homes.get("Ann Hill",{}),"F1 had been learnt as a way in")
check(any(abs(o)<600 for _,o,*_ in g.clocks.get("annhill",[])),"her own device keeps good time")

add_at(m,"Ann Hill","you lot are idiots",["F1","82","A6","5D"],time.time()-OFF); sync(g)
b=next((b for b in g.blocks.values() if b.get("source")=="spoof"),None)
check(b and b["value"]=="F1" and b["spoof"]["why"]=="device","held as a different device using her name")
check(b and "different device" in b["reason"],"the reason says so")
check("F1" not in g.homes.get("Ann Hill",{}),"F1 forgotten as one of her ways in")
check(act(m,"evening all","Ann Hill",["07"])=="allow","the real Ann gets through")

# a name whose own device always has a wrong clock is left alone
m2=mock(); g2=guard(m2,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(6): add_at(m2,"Old Clock",f"{words[i]} chat {i}",["07"],time.time()-OFF)
g2.apply_settings({"mode":"protect"}); sync(g2)
add_at(m2,"Old Clock","hello again",["F1","82","A6"],time.time()-OFF); sync(g2)
check(not any(b.get("source")=="spoof" for b in g2.blocks.values()),"a regular whose clock is always wrong is left alone")

# experiment off: nothing
m3=mock(); g3=guard(m3,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m3.add("Ann Hill",f"{words[i]} chat {i}",["07"],ago=6600-i*700)
g3.apply_settings({"mode":"protect"}); sync(g3)
add_at(m3,"Ann Hill","you lot are idiots",["F1","82"],time.time()-OFF); sync(g3)
check(not any(b.get("source")=="spoof" for b in g3.blocks.values()),"off: nothing")

# clock history saved, bad values rejected
g._save_state(force=True)
path=g.file_cfg.get("state_file", sg.DEFAULT_CONFIG["state_file"])
st=json.load(open(path)); check(st.get("clocks",{}).get("annhill"),"saved")
st["clocks"]={"annhill":[[int(time.time()),3],["x",1],[int(time.time())+999999,1],[True,1]]}; json.dump(st,open(path,"w"))
g.clocks.clear(); g._load_state()
check(g.clocks.get("annhill")==[[st["clocks"]["annhill"][0][0],3]],"bad clock records rejected")

# you hold a name from one repeater yourself
m4=mock(); g4=guard(m4,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m4.add("Ann Hill",f"{words[i]} chat {i}",["F1"] if i%2 else ["07"],ago=6600-i*700)
g4.apply_settings({"mode":"protect"}); sync(g4)
g4.action("hold_name_hop",{"sender":"Ann Hill","hop":"f1","channel":"Public"}); sync(g4)
b=next((b for b in g4.blocks.values() if b.get("source")=="manual" and b["kind"]=="imposter"),None)
check(b and b["value"]=="F1" and 6*86400<b["expires"]-time.time()<=7*86400,"held for 7 days")
check(act(m4,"hello","Ann Hill",["F1","82"])=="drop" and act(m4,"hello","Ann Hill",["07"])=="allow","only from that repeater")
check("F1" not in g4.homes.get("Ann Hill",{}),"no longer one of her ways in")
for bad in ({"sender":"?","hop":"F1"},{"sender":"Ann Hill","hop":"zz"},{"sender":"Ann Hill"}):
    try: g4.action("hold_name_hop",bad); check(False,f"refused {bad}")
    except ValueError: check(True,"")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
