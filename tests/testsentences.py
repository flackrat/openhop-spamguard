# Remembering spam sentences reused by throwaway names. Checked against openHop's own rule
# engine. All names and messages are made up.
import sys, logging, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PUB=sg.PUBLIC_CHANNEL_KEY
class P:
    def __init__(s,text,sender,path):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,PUB))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m,text,sender,path=["A1","B2"]):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(text,sender,path),{"payload_type":5,"hop_count":len(path),
        "route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
RANT="Nobody here asked for your widget company to own the whole hobby"
check(sg.SpamGuard.sentence_key("Good morning all!") is None and sg.SpamGuard.sentence_key("Morning") is None,"greetings never count")
check(sg.SpamGuard.sentence_key("@[Bob] see https://x.example/a then") is None,"mentions and links don't make a short reply long")
check(sg.SpamGuard.sentence_key("Nobody here, asked for YOUR widget company to own the whole hobby!!")==sg.SpamGuard.sentence_key(RANT),"case and punctuation don't matter")

m=mock(); g=guard(m,floodguard=False,remember_sentences=True,vary_limits=False)
g.apply_settings({"mode":"protect"}); sync(g)
# A regular who says the same long thing as the spammer is never counted
for i in range(8): m.add("Ann Hill",f"weather chat number {i} today",["4C"],ago=8000-i*700)
sync(g)
check(g.is_known("Ann Hill"),"Ann Hill is known")
# Two throwaway names on different days send the same rant
m.add("QX7%ZZ1A",RANT,["F1","72"],ago=1800); sync(g)
check(not any(b["kind"]=="text" and b["value"]==RANT for b in g.blocks.values()),"one name: nothing yet")
m.add("K2#LL0PQ",RANT+"!",["F1","04"],ago=60); sync(g)
b=[x for x in g.blocks.values() if x["kind"]=="text" and "fortnight" in x["reason"]]
check(len(b)==1,"a second unknown name, hours later: the sentence is held")
check(b and b[0]["expires"]-time.time()>6*86400,"for days, not minutes")
check(act(m,RANT,"ZZ9 NEW",["F1","72"])=="drop","a third throwaway name is stopped in openHop")
g.action("allow_sender",{"sender":"Ann Hill"}); sync(g)
names=[r.get("name","") for r in m.policy["policy_engine"]["rules"]]
ki=next(i for i,n in enumerate(names) if n.endswith("known-people")); si=next(i for i,n in enumerate(names) if ":sentence:" in n)
check(si>ki,"the sentence rule sits after the known-people rule, so people SpamGuard knows get through it")
check(g.gated(b[0]) and g.block_matches(b[0],sg.Event(ts=time.time(),sender="New One",text=RANT,path=["A1"],channel="Public")),"and SpamGuard's own count agrees")
check(act(m,"Good morning everyone","ZZ9 NEW")=="allow","ordinary greetings from new names are untouched")
m5=mock(); g5=guard(m5,floodguard=False,vary_limits=False); g5.apply_settings({"mode":"protect"}); sync(g5)
g5._add_block("sentence:t","text",RANT,"Sent by 2 different unknown names in the last fortnight","campaign",channel="Public",ttl=86400); g5.blocks["sentence:t"]["gate"]=True
sync(g5); check("links:new" not in g5.blocks,"a remembered sentence alone doesn't start holding links from new names")
g5._add_block("text:t2","text","buy cheap widgets today friends","test","campaign",channel="Public",ttl=3600); sync(g5)
check("links:new" in g5.blocks,"an ordinary campaign still does")
# Greetings from many new names never build up
m2=mock(); g2=guard(m2,floodguard=False,remember_sentences=True,vary_limits=False); g2.apply_settings({"mode":"protect"}); sync(g2)
for i in range(6): m2.add(f"New Person {i}","Good morning all",[f"{i:02X}"],ago=500-i)
sync(g2); check(not any("fortnight" in x["reason"] for x in g2.blocks.values()),"six people saying good morning: nothing held")
# Switched off
check(sg.DEFAULT_CONFIG["remember_sentences"] is True,"on by default")
m3=mock(); g3=guard(m3,floodguard=False,vary_limits=False,remember_sentences=False); g3.apply_settings({"mode":"protect"})
m3.add("QX7%ZZ1A",RANT,["F1"],ago=1800); m3.add("K2#LL0PQ",RANT,["F2"],ago=60); sync(g3)
check(not any("fortnight" in x["reason"] for x in g3.blocks.values()),"off: no fortnight block")
# Memory is bounded, forgotten after a fortnight, survives a restart
g._save_state(force=True); g4=sg.SpamGuard(dict(g.file_cfg))
check(sg.SpamGuard.sentence_key(RANT) in g4.sentences,"remembered after a restart")
for i in range(g.SENTENCES_MAX+50):
    e=sg.Event(ts=time.time(),sender=f"N{i}",text=f"word{i} another few words here please",path=["A1"],channel="Public"); g._note_sentence(e)
check(len(g.sentences)<=g.SENTENCES_MAX,"memory is capped")
k=next(iter(g.sentences)); g.sentences[k]["names"]={"x":time.time()-20*86400}; g.forget_old_names()
check(k not in g.sentences,"old sentences are forgotten")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
