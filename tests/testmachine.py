# 6.27.3: messages that are a program talking (a Reticulum bridge over a channel) are counted and labelled, and
# never held for being that. All names and data are made up.
import sys, os, base64, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
b64=lambda n: base64.urlsafe_b64encode(os.urandom(n)).decode().rstrip("=")
check(sg.machine_kind("RNS:"+b64(48))=="reticulum","an RNS: fragment is spotted")
check(sg.machine_kind(b64(75))=="encoded" and sg.machine_kind(base64.z85encode(os.urandom(76)).decode())=="encoded","a long unbroken encoded run is spotted")
for t in ("Morning all, repeater check from the hill","https://www.example.com/a/very/long/link/that/goes/on/and/on/and/on/and/on/forever12345","RNS: is a nice protocol","Supercalifragilisticexpialidocious"*3,"hello"):
    check(sg.machine_kind(t) is None,"ordinary text is not: %s"%t[:30])

m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i in range(5): m.add("Bridge Node One","RNS:"+b64(48),["4C","2F"],ago=300-i*30)
m.add("Plain Person","Anyone on the hill today?",["4C","2F"],ago=100)
cycle(g)
check(g.stats.get("machine",0)==5,"five machine messages counted (%s)"%g.stats.get("machine"))
check(g.status()["summary"]["machine_24h"]==5,"shown in the summary")
check(not any("machine" in str(b.get("reason","")).lower() for b in g.blocks.values()),"no block is written because it is machine traffic")
notes=[n for n in g.notes if "program talking" in str(n)] if hasattr(g,"notes") else []
check(len(notes)<=1,"mentioned once a day at most")
check(m.decide("Bridge Node One","RNS:"+b64(48),["4C","2F"])=="allow","a fresh fragment from a new name is passed on")
why=g._q_classify({"machine":"reticulum","known":False})
check(why[0]=="genuine" and "program talking" in why[1],"the Messages list explains it: %s"%(why,))
print("testmachine: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
