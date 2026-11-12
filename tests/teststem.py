# 6.27.3: made-up names behind a first repeater that keeps changing (even a trusted code) are caught by the route
# after it, and a repeat of a copy that a rule stopped on purpose is not counted as a retry. All names are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
TXT="Cheap watches and free prizes waiting for you on my page tonight"
NOISE=("P/M£<$£H","8KN_<%RV","I)*D6R<$",">8=2-A__","S</D_*_P","_HX4L<_:","Q,ZWX*%B")

# 1. Six keyboard-noise names, all through the same two repeaters after a first repeater that is a real, trusted code
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
m.add("Andy Example","Morning all",["73","8D"],ago=900); m.add("Andy Example","Anyone about?",["73","8D"],ago=800)
tails=(["04","F0","91","AD"],["04","F0","36","AD","79"],["04","F0","9C","76"],["04","F0","36","C2","09"],["04","F0","91","DB"],["04","F0","B1","91"])
for i,(n,t) in enumerate(zip(NOISE,tails)): m.add(n,"%s %d"%(TXT,i),["07"]+t,ago=200-i*20)
cycle(g); cycle(g)
stems=[k for k,b in g.blocks.items() if b["kind"]=="stem"]
check(stems==["stem:04>F0"],"six made-up names behind first repeater 07 start a stem block on 04>F0 (got %s)"%stems)
check(g.blocks["stem:04>F0"]["source"]=="rotation","it is a rotation-style block")
check("04>F0" in g.describe(g.blocks["stem:04>F0"]) and "except people" in g.describe(g.blocks["stem:04>F0"]),"described in plain words")
# 2. It catches a new made-up name under a different first repeater, in the rules openHop gets
check(m.decide("Z9QQ<K/A","Lovely views today, anyone out?",["DD","04","F0","91"])=="drop","a new name behind another first repeater is dropped")
check(m.decide("Andy Example","Anyone on the hill this morning?",["07","04","F0","91"])!="drop","a known person on the same route passes")
check(m.decide("Plain Person","Anyone about on the hill?",["DD","93","7E"])!="drop","other routes are untouched")
# 2b. Only routes about as long as the spam's: a stranger's message on a much longer journey through the same
# repeaters is left alone, in openHop and in SpamGuard's own count
long=["2A","31","5C","77","04","9E","F0","B3","C8","D1","E2","4F"]
check(g.blocks["stem:04>F0"].get("max_hops")==6+g.STEM_EXTRA_HOPS,"the block remembers how long the spam's routes were")
check(m.decide("Plain Person","Greetings from a long way off",long)!="drop","a long journey through the same repeaters is not held")
check(not g.block_matches(g.blocks["stem:04>F0"],sg.Event(ts=0,sender="Plain Person",text="x",path=long,channel="Public")),"and SpamGuard's own count agrees")

# 3. Four names are not enough; ordinary-looking names never count
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i,n in enumerate(NOISE[:3]): m.add(n,"%s %d"%(TXT,i),["07"]+tails[i],ago=200-i*20)
cycle(g)
check(not any(b["kind"]=="stem" for b in g.blocks.values()),"three made-up names are not enough")
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i,n in enumerate(("Hilltop Hiker","Brook Walker","Moss Ford","Tarn Reed","Fell Runner","Dale Keeper")): m.add(n,"Morning all number %d, anyone about?"%i,["07"]+tails[i],ago=200-i*20)
cycle(g)
check(not any(b["kind"]=="stem" for b in g.blocks.values()),"six ordinary names on the same route never start a stem block")

# 4. A route that three regulars depend on is never blocked
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
now=time.time()
for r in ("Reg One","Reg Two","Reg Three"):
    g.sender_history[r]={"first":now-5*3600,"count":30,"last":now-300,"hops":set()}
    m.add(r,"Evening all, anyone on the air?",["59","04","F0"],ago=100)
for i,n in enumerate(NOISE[:6]): m.add(n,"%s %d"%(TXT,i),["07"]+tails[i],ago=200-i*20)
cycle(g)
check(not any(b["kind"]=="stem" for b in g.blocks.values()),"three regulars behind the route: no stem block")

# 5. A copy a rule stopped on purpose, sent again, is not a retry; one that was lost is
T2="Morning all, is the Exmouth repeater working for anyone today?"
def pkt(m,sender,text,path,ago,h,**extra):
    m.add(sender,text,path,ago=ago); m.packets[-1]["packet_hash"]=h; m.packets[-1].update(extra)
m=mock(); g=guard(m, quick_resend_hold=True); g.apply_settings({"mode":"protect"}); g.me={"name":"me","hash":"A1"}
pkt(m,"Gil",T2,["4C"],40,"ee"*8,transmitted=False,drop_reason="Policy blocked by rule")
pkt(m,"Gil",T2,["4C"],20,"ff"*8,transmitted=True); cycle(g)
check(g.stats.get("retries",0)==0,"first copy stopped by a rule: the repeat is not a retry")
m=mock(); g=guard(m, quick_resend_hold=True); g.apply_settings({"mode":"protect"}); g.me={"name":"me","hash":"A1"}
pkt(m,"Hal",T2,["4C"],40,"ab"*8,transmitted=False)
pkt(m,"Hal",T2,["4C"],20,"cd"*8,transmitted=True); cycle(g)
check(g.stats.get("retries",0)==1,"first copy simply never passed on: still a retry")
print("teststem: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
