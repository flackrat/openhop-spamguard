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

m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(8): m.add("Ann Hill",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"] if i%3 else ["07","3B"],ago=6600-i*700)
for i in range(8): m.add("Bob Far",f"{words[i]} {words[(i*5)%11]} news {i}",["9C","1A","2B","3C","4D","5E","6F","70","81","92"],ago=6500-i*700)
g.apply_settings({"mode":"protect"}); sync(g)
check(g._local("Ann Hill") and not g._local("Bob Far"),"Ann is local, Bob is usually far")
check(not g.attack_on(time.time()),"no attack under way")

# a plain message under Ann's name from far away, through a repeater she never uses
m.add("Ann Hill","hello",FAR,ago=0); sync(g)
check(any(b["kind"]=="imposter" and b["value"]=="F1" and b.get("who")=="Ann Hill" for b in g.blocks.values()),
      "held from that repeater even though the text is ordinary")
check("F1" not in g.homes.get("Ann Hill",{}) and 9 not in g.near.get("annhill",[]),"not learnt as a way in")
check(act(m,"you lot are idiots","Ann Hill",FAR)=="drop","the next copy from there is dropped")
check(act(m,"evening all","Ann Hill",["07"])=="allow","the real Ann from her usual way in gets through")
check(act(m,"evening all","Ann Hill",["5B","07"])=="allow","and from somewhere else nearby")

# someone usually far away turning up through a new repeater: left alone
m.add("Bob Far","hello from the hills",["AA","1A","2B","3C","4D","5E","6F","70","81"],ago=0); sync(g)
check(not any(b["kind"]=="imposter" and b.get("who")=="Bob Far" for b in g.blocks.values()),"a far-off regular is left alone")

# what the hold says: whose name was copied and why
b=next(b for b in g.blocks.values() if b.get("source")=="spoof")
sp=b["spoof"]
check(sp["of"]=="Ann Hill" and sp["via"]=="F1" and sp["hops"]==9 and sp["usual_via"]=="07" and sp["why"]=="far","spoof details kept")
check("Copied name: Ann Hill is usually" in b["reason"] and "via F1" in b["reason"],"the reason says so in plain words")
check("copied name" in g.describe(b) and g.Q_REASON["spoof"],"described as a copied name")
check(g._q_classify({"caught_by":"x","caught_source":"spoof","caught_kind":"imposter"})[1]==g.Q_REASON["spoof"],"Messages shows why")
rec=[]; g.evidence=type("E",(),{"add":lambda self,r: rec.append(r),"flush":lambda self,**k: None})()
m.add("Ann Hill","still me, honest",FAR,ago=0); sync(g)
for x in g.events:
    if x.text=="still me, honest": x.ts-=200
g.log_messages(list(g.events))
r=next((r for r in rec if r.get("type")=="msg" and r.get("text")=="still me, honest"),None)
check(r and r["spoofed"]=="Ann Hill" and r["caught_source"]=="spoof","the evidence log names the spoofed name")
check(r and r["hash_bytes"]==1 and r["sent_offset_s"] is not None,"device clock and route code size recorded")

# a new spelling of a nearby name from far away is caught too
m.add("Ann-Hill","hello again",["F2","82","A6","5D","C1","3C","79","26","07"],ago=0); sync(g)
check(any(b.get("who")=="Ann-Hill" and b["value"]=="F2" for b in g.blocks.values()),"same family, different spelling")

# heard nearby and far off within ten minutes: the far one is the copy, even without much history
m2=mock(); g2=guard(m2,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(5): m2.add("Cal Moss",f"{words[i]} {words[(i*5)%11]} chat {i}",["07"],ago=6000-i*900)
g2.apply_settings({"mode":"protect"}); sync(g2)
check(not g2._local("Cal Moss"),"not enough history for the distance check")
m2.add("Cal Moss","anyone about?",["07"],ago=120); m2.add("Cal Moss","you are all idiots",["F1","82","A6","5D","C1","3C","79","26"],ago=0)
sync(g2)
b2=next((b for b in g2.blocks.values() if b.get("source")=="spoof"),None)
check(b2 and b2["spoof"]["why"]=="two places" and "also heard nearby" in b2["reason"],"two places at once")

# switched off: none of this happens
m3=mock(); g3=guard(m3,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=False)
check(sg.DEFAULT_CONFIG["spoof_watch"] is True,"on by default")
for i in range(8): m3.add("Ann Hill",f"{words[i]} {words[(i*3)%11]} chat {i}",["07"],ago=6600-i*700)
g3.apply_settings({"mode":"protect"}); sync(g3)
m3.add("Ann Hill","hello",FAR,ago=0); sync(g3)
check(not any(b.get("source")=="spoof" for b in g3.blocks.values()),"off: nothing held as spoofed")

# companion adverts are logged (with the check on), at most every 30 minutes each
import struct
def advert(name,key):
    return (bytes.fromhex(key)+struct.pack("<I",int(time.time()))+b"\x00"*64+bytes([0x81])+name.encode()).hex()
rec.clear()
k="AB"*32
for _ in range(3): g.learn_advert({"payload":advert("Ann Hill",k),"original_path":"07,3B","timestamp":time.time()})
ad=[r for r in rec if r.get("type")=="advert"]
check(len(ad)==1 and ad[0]["name"]=="Ann Hill" and ad[0]["key"]=="ABABABAB" and ad[0]["hops"]==2,"companion advert logged once")
# the hop history is saved and loaded, rejecting bad values
g._save_state(force=True)
path=g.file_cfg.get("state_file", sg.DEFAULT_CONFIG["state_file"])
st=json.load(open(path)); check(st.get("near",{}).get("annhill")==g.near["annhill"],"saved")
st["near"]={"annhill":[1,2,"x",99,-1,True,3]}; json.dump(st,open(path,"w"))
g.near.clear(); g.fam_names.clear(); g._load_state()
check(g.near.get("annhill")==[1,2,3],"bad hop counts rejected on load")

check(g.fam_names.get("annhill")>={"Ann Hill"},"name family saved and loaded")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
