# A name on Public sending one fixed text with a short changing part (a welcome bot greeting each newcomer) is a
# bot: held on Public for a day when bots are kept off Public, counted only when that is record-only. People
# chatting normally, trusted names and other channels are left alone. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
T=sg.shared_template
check(T("Welcome to the mesh Kip Ferris! from Quarry Relay","Welcome to the mesh Ada! from Quarry Relay"),"a greeting with the name changed is one template")
check(T("Morning all from the ridge","Evening all, quiet on the ridge tonight") is None,"ordinary chat is not")
check(T("Good morning","Good evening") is None,"too short to be a template")
check(T("Net tonight at 8, topic: antennas and feeders","Net tonight at 8, topic: batteries, solar and keeping the whole station running all winter long") is None,"a long changing part is not a template")
def run(g,m):
    for _ in range(2): g.poll_once(); g.last_sync=0; g.sync_pending=True
m=mock(); g=guard(m, public_bots=True, public_bots_log_only=False)
for i,n in enumerate(["Kip Ferris","Ada","Bram Holt","Juno"]):
    m.add("Quarry Greeter",f"Welcome to the mesh {n}! 👋 from Quarry Relay",["A1","B2"],ago=3000-i*600)
for i in range(6):
    m.add("Ren Tally",["Morning all","Anyone on the ridge?","Clear skies here","Off to work now","Back again","Night all"][i],["C3"],ago=2900-i*400)
run(g,m)
bk=[b for b in g.blocks.values() if b.get("source")=="pubbot"]
check(len(bk)==1 and bk[0]["value"]=="Quarry Greeter" and bk[0]["channel"]=="Public","the greeter is held on Public: %s"%[(b["value"],b.get("channel")) for b in bk])
check(bk and bk[0]["expires"]-bk[0]["created"]<=86400+5,"for a day")
check(any("like a bot" in a["msg"] for a in g.activity),"and Activity says why")
check(not any("Ren" in str(b.get("value")) for b in g.blocks.values()),"someone chatting normally is left alone")
# record-only: counted, not held
m2=mock(); g2=guard(m2, public_bots=True, public_bots_log_only=True)
for i,n in enumerate(["Kip","Ada","Bram"]): m2.add("Quarry Greeter",f"Welcome to the mesh {n}! 👋 from Quarry Relay",["A1"],ago=900-i*200)
run(g2,m2)
check(not any(b.get("source")=="pubbot" for b in g2.blocks.values()) and g2.stats["pubbots"]>=1,"record-only: counted, not held")
# trusted, or another channel: left alone
m3=mock(); g3=guard(m3, public_bots=True, public_bots_log_only=False, allow_senders=["Quarry Greeter"])
for i,n in enumerate(["Kip","Ada","Bram"]): m3.add("Quarry Greeter",f"Welcome to the mesh {n}! 👋 from Quarry Relay",["A1"],ago=900-i*200)
run(g3,m3)
check(not any(b.get("source")=="pubbot" for b in g3.blocks.values()),"a trusted name is left alone")
m4=mock(); g4=guard(m4, public_bots=True, public_bots_log_only=False, hashtag_channels=["#greet"])
for i,n in enumerate(["Kip","Ada","Bram"]): m4.add("Quarry Greeter",f"Welcome to the mesh {n}! 👋 from Quarry Relay",["A1"],ago=900-i*200,key=sg.hashtag_secret("greet"))
run(g4,m4)
check(not any(b.get("source")=="pubbot" for b in g4.blocks.values()),"another channel is left alone")
# off: nothing
m5=mock(); g5=guard(m5, public_bots=False)
for i,n in enumerate(["Kip","Ada","Bram"]): m5.add("Quarry Greeter",f"Welcome to the mesh {n}! 👋 from Quarry Relay",["A1"],ago=900-i*200)
run(g5,m5)
check(not any(b.get("source")=="pubbot" for b in g5.blocks.values()),"bots on Public switched off: nothing held")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
