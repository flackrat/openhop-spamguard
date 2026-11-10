# 6.29.1: symbol junk no longer counts as genuine-looking held (it stalled auto-protect on a fresh install);
# a known name flooding or repeating only through repeaters that person never uses is held from there, not
# everywhere, and not counted against them; keyboard-mashed names never become known by sending quiet messages.
# Checked against openHop's own rule engine. All names and messages are made up.
import sys, logging
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
JUNK=[("J,YSY*%Z","YF^;ri}12`Rnue/"),("Q#$Q3<M=","CT[36%X+{/%!R"),("H=UC(#0P","m{\\F^yG,tz"),("E1N%2(1D","}<hZy\\NI*ER"),("PQ;RS",".hC*6JrB`M9SEz")]

# 1. Symbol junk is spam, not "possibly genuine": a fresh install in Monitor still switches itself on
m=mock(); g=guard(m,floodguard=False,symbol_junk=True,mode="monitor")
g.monitor_since=time.time()-1; sync(g)
for n,t in JUNK:
    m.add(n,t,["9A","4C"],ago=0); sync(g)
check(all(e.matched=="junk:symbols" for e in list(g.events)[-5:]),"the junk was caught")
st=g.auto_protect_status()
check(st["held"]==0 and not st["waiting"],f"not counted as genuine-looking held: {st}")
q=g._q_classify({"caught_by":"junk:symbols","caught_source":"junk","caught_kind":"links"})
check(q[0]=="stopped","shown as stopped spam in Messages")

# 2. Someone copying a known name floods from far away: the person is not blocked, not counted against
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m.add("Ann Hill",f"Morning all, chat {i}",["4C","2F"],ago=7200-i*600)
g.apply_settings({"mode":"protect"}); sync(g)
check(g.is_known("Ann Hill") and sum(g.homes.get("Ann Hill",{}).values())>=5,"Ann is known with a usual way in")
for i in range(16): m.add("Ann Hill",f"buy cheap stuff number {i} now",["9A","77"],ago=500-i*20)
sync(g)
kinds={b["kind"] for b in g.blocks.values() if b.get("source")!="dedupe"}
check("burst" not in kinds,"no block on her name everywhere")
check(any(b["kind"]=="imposter" and b["value"]=="9A" and b.get("who")=="Ann Hill" for b in g.blocks.values()),
      "her name is held from the repeater the flood came in by")
check(act(m,"Anyone up for the net tonight?","Ann Hill",["4C","2F"])=="allow","the real Ann from her usual way in gets through")
check(act(m,"buy cheap stuff number 99 now","Ann Hill",["9A","77"])=="drop","the copy from the flood's repeater is dropped")
check(not g.offences.get("Ann Hill"),"not counted as an offence against her")

# 3. The same line again and again under her name from somewhere else far away: not counted against her either
for i in range(4): m.add("Ann Hill","this exact line again and again",["5B","77"],ago=60-i*5)
sync(g)
check(any(b["kind"]=="repeat" for b in g.blocks.values()),"the repeated line is still held")
check(not g.offences.get("Ann Hill") and g.is_known("Ann Hill"),"she keeps her known pass")

# 4. A real burst from her own way in is still held as before
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m.add("Bob Lee",f"Evening all, chat {i}",["4C","2F"],ago=7200-i*600)
g.apply_settings({"mode":"protect"}); sync(g)
for i in range(16): m.add("Bob Lee",f"message number {i} from bob",["4C","2F"],ago=500-i*20)
sync(g)
check(any(b["kind"]=="burst" and b["value"]=="Bob Lee" for b in g.blocks.values()),"a burst from the person's usual way in is held as before")

# 5. Keyboard-mashed names never become known; ordinary and non-Latin names still do
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for n in ("Q#'O7(4X","イワシ養殖業者 🐟","Pat Moss"):
    for i in range(4): m.add(n,f"hello there, message {i}",["4C","2F"],ago=7200-i*900)
sync(g)
check(not g.is_known("Q#'O7(4X"),"a keyboard-mashed name sending quiet messages is not known")
check(g.is_known("イワシ養殖業者 🐟") and g.is_known("Pat Moss"),"ordinary and non-Latin names still become known")
check(sg.noise_name("Q#'O7(4X") and sg.noise_name("$*£)#>YB") and not sg.noise_name("イワシ養殖業者 🐟"),"name shape")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
