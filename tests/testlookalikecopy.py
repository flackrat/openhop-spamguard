# Copied-name check: history, people with similar names, and a person's own device. All names and messages are made up.
import sys, logging, time, json, os
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
def add_at(m,sender,text,path,sent,ago=0):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":5,
        "payload":enc(sender,text,sg.PUBLIC_CHANNEL_KEY,sent=sent),
        "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})
FAR=["E7","9B","2D","6A","C5","1F","8E","D3","4C"]
HOME2=["9C","1A","2B","3C","4D","5E","6F","70","81","92"]
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
def regular(m,name,path=None,n=8):
    for i in range(n): m.add(name,f"{words[i%11]} {words[(i*3)%11]} chat {i}",path or (["4C"] if i%3 else ["4C","5E"]),ago=6600-i*700)
def held(g,who=None): return [b for b in g.blocks.values() if b["kind"]=="imposter" and (who is None or b.get("who")==who)]

# A far copy through a repeater the person never uses is held, and a flood of copies doesn't rewrite who they are
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
regular(m,"Sam Lowmesh"); g.apply_settings({"mode":"protect"}); sync(g)
check(g._local("Sam Lowmesh"),"Sam is a nearby regular")
m.add("Sam-Lowmesh","hello",FAR,ago=0); sync(g)
check(any(b["value"]=="E7" for b in held(g,"Sam-Lowmesh")),"copy held from that repeater")
for i in range(6): m.add(["Sam-Lowmesh","SamLowmesh","Sam Lowmesh"][i%3],f"{words[i]} {i} nonsense",FAR[:8+i%2]+["4C"],ago=0)
sync(g)
check("E7" not in g._family_homes("Sam Lowmesh"),"never learnt as a way in")
check(g._usual_hops("Sam Lowmesh") is not None and g._usual_hops("Sam Lowmesh")<=g.LOCAL_HOPS,"usual distance unchanged")
check(act(m,"another one","Sam-Lowmesh",FAR)=="drop","that spelling is dropped from there")
check(act(m,"evening all","Sam Lowmesh",["4C"])=="allow","the real person from the usual way in gets through")
check(act(m,"evening all","Sam Lowmesh",["5B","4C"])=="allow","and from somewhere else nearby")
check(act(m,"hello","Bob Stone",FAR)=="allow","an unrelated name from there is not held")

# A hold that keeps catching copies stays on, but only for a few hours
b=next(b for b in g.blocks.values() if b.get("source")=="spoof" and b["value"]=="E7")
b["expires"]=time.time()+60
m.add(b["who"],"still here",FAR,ago=0); sync(g)
check(b["expires"]>time.time()+3000,"kept on while it is still catching copies")
check(b["expires"]<=b["created"]+g.SPOOF_HOLD_MAX+1,"but no longer than a few hours from when it started")

# Different people whose names only start alike are separate people
check(g.name_family("Peter Jones")!=g.name_family("Peter Brown"),"same first name, different people")
check(g.name_family("Sam Lowmack")!=g.name_family("Sam Lowmesh"),"a different spelling is a different name")
m2=mock(); g2=guard(m2,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
regular(m2,"Sam Lowmesh"); g2.apply_settings({"mode":"protect"}); sync(g2)
n_held=0
for i in range(6):
    m2.add("Sam Lowmeadow",f"{words[i]} {words[(i*5)%11]} hello from my own town {i}",HOME2,ago=0); sync(g2)
    n_held+=act(m2,"another hello","Sam Lowmeadow",HOME2)=="drop"
check(not held(g2,"Sam Lowmeadow") and n_held==0,"a far-away newcomer with a similar name is not held")

# Many names don't merge people or lose anyone's history
for i in range(7000): g2.name_family(f"filler{i:05d}name")
check(g2._local("Sam Lowmesh"),"a nearby regular is still nearby after thousands of other names")

# A person's own device clock going wrong at their main way in is not treated as a copy
m3=mock(); g3=guard(m3,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True)
for i in range(8): add_at(m3,"Ann Hill",f"{words[i]} {words[(i*3)%11]} chat {i}",["4C"],time.time()-(6600-i*700),ago=6600-i*700)
g3.apply_settings({"mode":"protect"}); sync(g3)
add_at(m3,"Ann Hill","clock went wrong, morning all",["4C","5E"],time.time()-254*86400); sync(g3)
check(not held(g3,"Ann Hill"),"own clock reset at home: not held")
check("4C" in g3.homes.get("Ann Hill",{}),"and her way in is kept")
check(act(m3,"still me","Ann Hill",["4C"])=="allow","she still gets through")

# Switched off: nothing is held as spoofed
m4=mock(); g4=guard(m4,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=False)
regular(m4,"Sam Lowmesh"); g4.apply_settings({"mode":"protect"}); sync(g4)
m4.add("Sam-Lowmesh","hello",FAR,ago=0); sync(g4)
check(not any(b.get("source")=="spoof" for b in g4.blocks.values()),"off: nothing held as spoofed")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
