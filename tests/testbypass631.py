# 6.31.0: more ways round SpamGuard from a private review, each closed or narrowed. Copies disguised so no text
# rule can match (capitals flipped, invisible characters) bring a short newcomer hold; invisible spaces are junk;
# links without http are links; long @[...] brackets are read; a paused lockdown still holds the entry
# repeaters; a busy repeater gets a narrow route block on one sign; fresh repeater adverts can't make a code look
# shared; a spam mark ends the long-standing pass; quiet-time copy checks need less history; you can mute a name.
# Checked against openHop's own rule engine. All names and messages are made up.
import sys, logging, random
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
class P:
    def __init__(s,text,sender,path,key=None):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,key or sg.PUBLIC_CHANNEL_KEY))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m,text,sender,path,key=None):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(text,sender,path,key),{"payload_type":5,"hop_count":len(path),
        "route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
NAMES=["Dave Smith","Paul Jones","Mike Brown","Tony Green","Steve White"]
ROUTES=[["4C"],["2F"],["7A"],["5B"],["1D"]]
BASE="The people running this mesh are frauds and liars, do not trust them"
random.seed(3)
def flip(t): return "".join(c.upper() if random.random()<0.15 else c for c in t)
def joiners(t): return "".join(c+("⁠" if random.random()<0.15 else "") for c in t)

# 1. Disguised copies: a short newcomer hold, since no text rule can match the next copy
for label,f in (("capitals flipped",flip),("word joiners sprinkled",joiners)):
    m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
    for i,n in enumerate(NAMES):
        m.add(n,f(BASE),ROUTES[i],ago=300-i*30); sync(g)
    check(g.blocks.get("lockdown",{}).get("source")=="auto-lockdown" and "disguised" in g.blocks["lockdown"]["reason"],
          f"{label}: newcomer hold started")
    check(sum(act(m,f(BASE),"Gary Hall",["6E"])=="drop" for _ in range(10))==10,f"{label}: the next copies are stopped")
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
for i,n in enumerate(NAMES):
    m.add(n,BASE,ROUTES[i],ago=300-i*30); sync(g)
check("lockdown" not in g.blocks,"plain copies get a text rule, not a newcomer hold")
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
for i,(n,t) in enumerate(zip(NAMES,["Morning all!","morning all","Morning All","MORNING ALL","morning all :)"])):
    m.add(n,t,ROUTES[i],ago=300-i*30); sync(g)
check("lockdown" not in g.blocks,"everyday greetings in different capitals start nothing")

# 2. Invisible spaces sprinkled through a message from a new name: held from the first message
m=mock(); g=guard(m,floodguard=False,symbol_junk=True); g.apply_settings({"mode":"protect"}); sync(g)
zw="".join(c+("​" if i%6==0 else "") for i,c in enumerate(BASE))
check(act(m,zw,"Gary Hall",["6E"])=="drop","invisible spaces from a new name are held")
check(act(m,"¯⁠\\⁠_(⁠ツ)⁠_/¯ oh well","Gary Hall",["6E"])=="drop","(kaomoji with a backslash is junk as before)")
check(act(m,"(⁠◔⁠‿⁠◔⁠) nice one","Gary Hall",["6E"])=="allow","a kaomoji using word joiners is passed on")
check(act(m,"👨‍👩‍👧 family day out","Gary Hall",["6E"])=="allow","emoji joined with the emoji joiner are passed on")

# 3. Links without http or www
check(sg.first_link("go to cheapstuff4u.com/deals/today now")=="cheapstuff4u.com/deals/today","a bare link is a link")
check(sg.first_link("I like the BBC website")is None and sg.first_link("version 1.2.3 out")is None,"ordinary text is not")
m=mock(); g=guard(m,floodguard=False,hold_links="always"); g.apply_settings({"mode":"protect"}); sync(g)
for t in ("cheapstuff4u.com/deals now","see cheapstuff4u dot com today","visit cheapstuff4u[.]com"):
    check(act(m,t,"Gary Hall",["6E"])=="drop",f"held: {t}")
check(act(m,"see the BBC weather for tomorrow","Gary Hall",["6E"])=="allow","ordinary chat passed on")

# 4. Long wordy @[...] brackets are read whatever surrounds them
s="hello there everyone @[This repeater network is run by frauds and liars]"
check(sg.smuggled(s) and "frauds" in sg.normalise(s),"a wordy bracket is read")
check(not sg.smuggled("@[Mobile - MC - V4] hello there everyone, good signal tonight"),"a real name in brackets is not")

# 5. While automatic lockdowns are paused, a flood gets holds on the repeaters it comes in by
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
g.suppressed["lockdown"]=time.time()+7200
hops=["11","22","33","44","55","66","77"]
for i in range(14): m.add(rname(),f"{rname()} {rname()}",[hops[i%7],"4C"],ago=10)
sync(g)
eb=[h for h in hops if f"hop:{h}" in g.blocks]
check("lockdown" not in g.blocks and len(eb)==7,f"entry repeaters held instead of a lockdown ({len(eb)})")

# 6. A busy repeater: a narrow route block on one sign
m=mock(); g=guard(m,floodguard=False,hop_prefer_route=False)
for p in range(6):
    for i in range(4): m.add(f"Regular {p}",f"hello from regular {p}, number {i}",["4C","2F"],ago=5000-i*300)
g.apply_settings({"mode":"protect"}); sync(g)
for i in range(4): m.add(rname(),f"made up {rname()}",["4C","9D"],ago=60-i)
sync(g)
check("hop:4C" not in g.blocks and "route:4C>9D" in g.blocks,"the spam's route is held, not the whole repeater")
check(act(m,"Evening all","Regular 1",["4C","2F"])=="allow" and act(m,"Hi, I'm new here","Pat Moss",["4C","2F"])=="allow",
      "people on other routes through it get through")

# 7. Fresh repeater adverts can't make a code look shared for blocking
m=mock(); g=guard(m,floodguard=False); now=time.time()
for k,t in (("4CAA11",now-86400),("4CBB22",now-60),("4CCC33",now-30)):
    g.node_ids[k]=now; g.node_first[k]=t
check(g.code_confidence("4C")=="ambiguous","shown as shared on the map")
check(g.code_confidence("4C",settled=True)=="confirmed","but for blocking, adverts heard just now don't count")

# 8. A spam mark ends a long-standing name's pass for keyboard junk
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m.add("Ann Hill",f"Morning all, chat {i}",["4C","2F"],ago=7200-i*600)
sync(g); g.known["Ann Hill"][0]-=8*86400; g.known["Ann Hill"][2]=40
check(g.settled("Ann Hill"),"long-standing")
g.action("label",{"label":"spam","sender":"Ann Hill","text":"x {y}","packet":"p1"})
check(not g.settled("Ann Hill"),"not after you mark one of their messages as spam")

# 9. Quiet-time copy check: a name with 10 or more messages from its usual way in
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
for i in range(11): m.add("Ann Hill",f"{words[i]} {words[(i*3)%11]} talk {i}",["4C","2F"],ago=6600-i*590)
g.apply_settings({"mode":"protect"}); sync(g)
m.add("Ann Hill","everyone go to http://example.invalid/free now",["9A","77"],ago=0); sync(g)
check(any(b["kind"]=="imposter" and b["value"]=="9A" for b in g.blocks.values()),"a copy of a newer regular is held from the new repeater")

# 10. Mute a name you choose, on one channel, for a few days
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m.add("Ann Hill",f"Morning all, chat {i}",["4C","2F"],ago=7200-i*600)
g.apply_settings({"mode":"protect"}); sync(g)
r=g.action("mute",{"sender":"Ann Hill","channel":"Public","days":7}); sync(g)
b=next((b for k,b in g.blocks.items() if k.startswith("mute:")),None)
check(b and b["kind"]=="burst" and 6*86400<b["expires"]-time.time()<=7*86400,"muted for 7 days")
check(act(m,"Morning all","Ann Hill",["4C","2F"])=="drop","held even though known")
check(act(m,"Morning all","Ann Hill",["4C","2F"],key=sg.hashtag_secret("#test"))=="allow","other channels untouched")
g.action("unblock",{"key":next(k for k in g.blocks if k.startswith("mute:"))}); sync(g)
check(act(m,"Morning all","Ann Hill",["4C","2F"])=="allow","removed by hand")
try: g.action("mute",{"sender":"?"}); check(False,"needs a real name")
except ValueError: check(True,"")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
