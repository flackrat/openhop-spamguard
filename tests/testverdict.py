import sys, logging, time, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,m):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",m)
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
# campaign establishes a text block
for i in range(4): m.add(rname(),"Buy cheap stuff now at the shop xyz",["6F","04"],ago=600-i)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(any(b["kind"]=="text" for b in g.blocks.values()),"text block exists")
for b in g.blocks.values(): b["created"]-=1000
# two more copies arrive after the block existed: openHop forwards one (the bug) and drops the other
def add(sender,tx,drop):
    h=os.urandom(8).hex()
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-200,"type":5,"payload":enc(sender,"Buy cheap stuff now at the shop xyz"),
        "packet_hash":h,"original_path":json.dumps(["6F","04"]),"transmitted":tx,"drop_reason":drop})
    return h
h1=add(rname(),True,None); h2=add(rname(),False,"Policy blocked packet (rule 9100)")
# a duplicate row of h2 that was forwarded later
m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-198,"type":5,"payload":m.packets[-1]["payload"],"packet_hash":h2,"original_path":json.dumps(["6F","71","04"]),"transmitted":True,"drop_reason":None})
g.poll_once(); g.poll_once()
check(g.verdict.get(h1)==[True,False],"verdict h1 "+str(g.verdict.get(h1)))
check(g.verdict.get(h2)==[True,True],"verdict h2 dup forwarded "+str(g.verdict.get(h2)))
mt=g.metrics(); print("d1",{k:mt["d1"][k] for k in ("c","x","l","spam")})
check(mt["d1"]["l"]==2,"both counted as leaks")
st=g.status(); check(st["metrics"]["d1"]["l"]==2,"status carries leaks")
print(f"{ok}/{ok+fail} passed")
