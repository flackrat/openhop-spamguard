# 6.45.0: telling a person from someone copying their name by the direction their messages come from (the hops just
# after the first), so a copy that shares the person's first repeater is still recognised, shown and held by its own
# repeater. Checked against openHop's own rule engine. All names, routes and messages are made up.
import sys, logging, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def add_at(m,sender,text,path,sent,ago=0):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":5,"payload":enc(sender,text,sg.PUBLIC_CHANNEL_KEY,sent=sent),
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
OFF=265*86400
REAL=[["CF","19","73","B0"],["6E","19","B5","73"],["6D","19","31","C7"]]
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar","rain"]

def setup(two_days=True, **kw):
    m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=True,**kw)
    for i in range(12):
        ago=7000-i*500
        add_at(m,"Moor Walker",f"{words[i]} chat {i}",REAL[i%3],time.time()-ago+20,ago=ago)
    g.apply_settings({"mode":"protect"}); sync(g)
    if two_days and g.dirs.get("moorwalker"):
        today=int(time.time()//86400); g.dirs["moorwalker"]["dd"]=[today-1,today]   # as if she was also heard yesterday
    return m,g

m,g=setup()
d=g.dirs.get("moorwalker")
check(d and d["n"]>=g.DIR_MIN,"her direction learnt from her own messages")
check(g.is_known("Moor Walker"),"known")
check("CF" in g.usual_ways("Moor Walker"),"CF is one of her usual first repeaters")

# a copy through the same first repeater, then a different direction, from another device
add_at(m,"Moor Walker","you are all idiots",["CF","5D","82","91"],time.time()-OFF); sync(g)
e=g.events[-1]
check(e.direction=="new" and e.copy and e.copy["level"]=="red" and "device" in e.copy["signs"],"seen as a probable copy")
b=next((b for b in g.blocks.values() if b["kind"]=="imposter" and b.get("who")=="Moor Walker"),None)
check(b and b["value"]=="5D","held by the copy's own repeater, not the shared first one")
check(b and 2.9*86400<b["expires"]-time.time()<=3*86400+5,"held for three days")
check(act(m,"hello all","Moor Walker",["CF","19","73"])=="allow","the real person through the same first repeater still gets through")
check(act(m,"hello all","Moor Walker",["6E","19","B5"])=="allow","...and from her other ways")
check(act(m,"more abuse","Moor Walker",["CF","5D","34"])=="drop","later copies that way are held")
check(act(m,"hello","Someone Else",["CF","5D","82"])=="allow","nobody else is held by it")
check("5D" in g.dirs["moorwalker"]["bad"],"that way remembered as a copy's")
add_at(m,"Moor Walker","still at it",["CF","5D","34"],time.time()+5); sync(g)
check("earlier" in (g.events[-1].copy or {}).get("signs",[]),"a later copy that way, even with its clock right, is red as an earlier copy's way")

# a new direction from her own device (clock right): shown, never held
before=len([b for b in g.blocks.values() if b["kind"]=="imposter"])
add_at(m,"Moor Walker","trying a new antenna",["CF","D7","E2"],time.time()+15); sync(g)
e=g.events[-1]
check(e.direction=="new" and e.copy and e.copy["level"]=="amber","her own device from somewhere new is amber")
check(len([b for b in g.blocks.values() if b["kind"]=="imposter"])==before,"and nothing is held for it")

# People: copied filter, banner data, warmth stays cool for the real person
pp=g.people({"show":"copied"})
row=next((r for r in pp["rows"] if r["name"]=="Moor Walker"),None)
check(row is not None and pp["counts"]["copied"]>=1,"listed under Name copied")
c=row["copies"] if row else {}
check(c and c["red"]>=1 and any(o["route"]=="CF>5D" and o["level"]=="red" for o in c["others"]),"the copy's direction shown red")
check(c and any(o["route"]=="CF>D7" and o["level"]=="amber" for o in c["others"]),"the new direction shown amber")
check(c and any(u["route"]=="CF>19" for u in c["usual"]),"her usual directions shown")
check(c and c["holds"] and c["holds"][0]["hop"]=="5D","the hold is shown")
check(row and row["warmth"]["level"]=="green","the real person still looks genuine")
check(row and "a different device" in next(o for o in c["others"] if o["route"]=="CF>5D")["signs"],"in words")

# forgetting the name keeps it on the list while it is being copied
g.action("forget_known",{"name":"Moor Walker"})
check(any(r["name"]=="Moor Walker" for r in g.people({"show":"copied"})["rows"]),"still shown after Forget")


# Spoofed on a copy through the shared first repeater holds the copy's own repeater
m2,g2=setup()
add_at(m2,"Moor Walker","rude words",["CF","3E","3C","88"],time.time()+20); sync(g2)
r=g2.action("spoofed",{"sender":"Moor Walker","text":"rude words","path":"CF>3E>3C>88","channel":"Public"}); sync(g2)
b=next((b for b in g2.blocks.values() if b["kind"]=="imposter" and b.get("who")=="Moor Walker"),None)
check(b and b["value"]=="3E","Spoofed holds the copy's repeater, not her own first one")
check("3E" in str(r.get("message","")),"and says which")
check(act(m2,"hi","Moor Walker",["CF","19","73"])=="allow" and act(m2,"x","Moor Walker",["CF","3E","3C"])=="drop","only the copy is held")
add_at(m2,"Moor Walker","more rude words",["CF","3E","77"],time.time()+20); sync(g2)
e=g2.events[-1]
check(e.copy and e.copy["level"]=="red" and "marked" in e.copy["signs"],"later messages that way are red, as you marked")

# a hold made automatically ends when her own device is heard that way from her own direction (her route changed)
m3,g3=setup()
add_at(m3,"Moor Walker","copy",["CF","5D","82"],time.time()-OFF); sync(g3)
b=next((b for b in g3.blocks.values() if b["kind"]=="imposter"),None)
check(b and b["value"]=="5D","held")
add_at(m3,"Moor Walker","copy with its clock put right",["CF","5D","82"],time.time()+10); sync(g3); sync(g3)
check(any(x["kind"]=="imposter" for x in g3.blocks.values()),"a copy with a right clock from its own direction doesn't end the hold")
add_at(m3,"Moor Walker","I'm visiting friends",["CF","19","5D","82"],time.time()+10); sync(g3); sync(g3)
check(act(m3,"hi","Moor Walker",["CF","19","5D"])=="allow","she gets through that way again")
check(not any(x["kind"]=="imposter" and x.get("source")=="spoof" for x in g3.blocks.values()),"her own device that way ends the hold")
check("5D" not in g3.dirs["moorwalker"]["bad"],"and that way is no longer a copy's")

# Not spam on a held copy: asked first, and if you go ahead the hold that way is lifted
m5,g5=setup()
add_at(m5,"Moor Walker","copy one",["CF","5D","82"],time.time()-OFF); sync(g5)
add_at(m5,"Moor Walker","copy two",["CF","5D","82"],time.time()-OFF); sync(g5)
e=g5.events[-1]; key=e.matched
check(key and g5.blocks[key]["kind"]=="imposter","the second copy was held")
body={"verdict":"not_spam","sender":"Moor Walker","text":"copy two","path":"CF>5D>82","channel":"Public","matched":key,"status":"held"}
r=g5.give_verdict(dict(body))
check(r.get("confirm") and "someone else using the name" in r["confirm"],"asked before trusting a name on a held copy")
check(key in g5.blocks,"nothing done before you answer")
r=g5.give_verdict(dict(body,confirm=True)); sync(g5)
check(key not in g5.blocks and "5D" not in g5.dirs["moorwalker"]["bad"],"if you say it was them, the hold and the copy way go")
check("removed" in r.get("message",""),"and it says so")

# a real new route settles in after two days with nothing against it
m4,g4=setup()
add_at(m4,"Moor Walker","new road 1",["CF","A1","A2"],time.time()+30); sync(g4)
check(g4.events[-1].direction=="new","a new route is new at first")
pd=g4.dirs["moorwalker"]["pend"]; k=next(iter(pd)); pd[k]=[x-1 for x in pd[k]]   # as if first seen yesterday
add_at(m4,"Moor Walker","new road 2",["CF","A1","A2"],time.time()+30); sync(g4)
add_at(m4,"Moor Walker","now usual",["CF","A1","A2"],time.time()+30); sync(g4)
check(g4.events[-1].direction=="usual","a new route seen on two days becomes usual")

# a burst on one day isn't a baseline: nothing is judged until a second day
m7,g7=setup(two_days=False)
add_at(m7,"Moor Walker","copy on day one",["CF","5D","82"],time.time()-OFF); sync(g7)
check(g7.events[-1].direction is None and not any(b["kind"]=="imposter" for b in g7.blocks.values()),"one day of messages: direction not judged yet")
check(g7.dirs["moorwalker"]["n"]>=g7.DIR_MIN and len(g7.dirs["moorwalker"]["dd"])==1,"(though enough messages were learnt)")

# a new direction that other names' spam has used never settles in as hers
m8,g8=setup()
g8.route_history=lambda path,who=None:{"spam":3,"spoof":0,"known":0}   # other unknown names sent spam that way
for k in range(3):
    add_at(m8,"Moor Walker",f"via the spam route {k}",["CF","B1","B2"],time.time()+20); sync(g8)
    pd=g8.dirs["moorwalker"]["pend"]
    for key in pd: pd[key]=[x-1 for x in pd[key]]   # as if each was a day apart
e=g8.events[-1]
check(e.direction=="new" and e.copy and "route" in e.copy["signs"],"still a new direction, with the spam-route sign")
check(not any(x in g8.dirs["moorwalker"]["h"] for x in ("B1","B2")),"and it never became one of her usual ways")
check(not any(b["kind"]=="imposter" for b in g8.blocks.values()),"(shown only, nothing held)")

# device clock boundaries
for off,red in ((sg.SpamGuard.CLOCK_OFF-120,False),(sg.SpamGuard.CLOCK_OFF+120,True)):
    m9,g9=setup()
    add_at(m9,"Moor Walker","clock test",["CF","5D","82"],time.time()-off); sync(g9)
    e=g9.events[-1]
    check(e.direction=="new" and (e.copy["level"]=="red")==red,f"a clock {'over' if red else 'under'} a day out is {'' if red else 'not '}another device")
    check(any(b["kind"]=="imposter" for b in g9.blocks.values())==red,f"and {'is' if red else 'is not'} held")
# her own replacement device, clock unset, heard her usual way: nothing happens
m10,g10=setup()
add_at(m10,"Moor Walker","new radio, clock not set",["6E","19","B5"],time.time()-OFF); sync(g10)
e=g10.events[-1]
check(e.direction=="usual" and e.copy is None and not any(b["kind"]=="imposter" for b in g10.blocks.values()),"her new device her usual way: not a copy")
# her replacement device from somewhere new: amber at most until a copy way is known
add_at(m10,"Moor Walker","on holiday",["CF","D7","E2"],time.time()+10); sync(g10)
check(g10.events[-1].copy["level"]=="amber","her own clock, somewhere new: shown, not held")

# a name with no history is never judged; the check off learns nothing
m5,g5=setup(); add_at(m5,"Brand New","hello",["CF","5D","82"],time.time()-OFF); sync(g5)
check(g5.events[-1].direction is None and not any(b.get("who")=="Brand New" for b in g5.blocks.values()),"no history, no judgement")
m6=mock(); g6=guard(m6,floodguard=False,known_min_msgs=3,known_min_minutes=60,spoof_watch=False)
for i in range(12): m6.add("Moor Walker",f"{words[i]} {i}",REAL[i%3],ago=7000-i*500)
g6.apply_settings({"mode":"protect"}); sync(g6)
check(not g6.dirs,"check off: nothing learnt")

# warmth
check(g.warmth("x","trusted")["level"]=="green" and g.warmth("x","held")["level"]=="red","warmth follows standing")
g.mark_counts["Lucky Prize"]=[3,0,time.time()]
w=g.warmth("Lucky Prize","known"); check(w["level"] in ("amber","red") and "marked as spam by you" in w["why"],"spam marks warm a name")
g.allow_senders.add("Lucky Prize"); check(g.warmth("Lucky Prize","trusted")["score"]<=15,"trusted stays cool"); g.allow_senders.discard("Lucky Prize")

# saved and reloaded; bad records rejected
g._save_state(force=True)
path=g.file_cfg.get("state_file", sg.DEFAULT_CONFIG["state_file"])
st=read_state(path); check(st.get("dirs",{}).get("moorwalker",{}).get("n",0)>=g.DIR_MIN,"saved")
st["dirs"]["junk"]={"h":{"AA":"x","BB":True,"CC":2},"n":9,"last":1e20,"bad":["ZZ","5d",3],"copies":[[1,"x","red",[]],"bad"],"pend":{"x":["a",1]}}
st["dirs"]["empty"]={"h":{"CC":2},"n":"9"}
st["dirs"]["notadict"]=[1,2]
write_state(path,st); g.dirs.clear(); g._load_state()
check(g.dirs.get("moorwalker",{}).get("n",0)>=g.DIR_MIN,"reloaded")
j=g.dirs.get("junk")
check(j and j["h"]=={"CC":2} and j["n"]==9 and j["last"]==0 and j["bad"]==["5D"] and j["copies"]==[] and j["pend"]=={"x":[1]},"bad values rejected")
check("notadict" not in g.dirs and "empty" not in g.dirs,"a record that isn't a dict, or holds nothing, is dropped")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
