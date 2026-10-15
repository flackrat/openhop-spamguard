# "Clear automatic blocks" must stick: the same evidence must not rebuild them straight away
# (testers saw cleared blocks "come back"). Manual blocks stay. Rule names in openHop say what each
# rule stops and whether it was added by hand or made by SpamGuard. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
g.action("block_text",{"text":"cheap antennas here"})
for i in range(5):
    m.add(rname(),"Free crypto giveaway join now at the link",["9D","2F"],ago=200-i*20)
m.add("Hilltop Hiker","Is the repeater on the church tower back up yet?",["A7","2F"],ago=50)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
auto=[k for k,b in g.blocks.items() if b.get("source")!="manual"]
check(len(auto)>0,"spam made automatic blocks: "+str(list(g.blocks)))
names=[r.get("name","") for r in m.policy["policy_engine"]["rules"] if r.get("name","").startswith("spamguard:")]
check(any("(yours)" in n and "cheap antennas" in n for n in names),"manual rule name says yours and what it stops: "+str(names))
check(any("(duplicate)" in n or "(campaign)" in n or "(auto)" in n for n in names),"automatic rule names say so: "+str(names))
g.action("clear_auto",{})
check(all(b.get("source")=="manual" for b in g.blocks.values()),"only manual blocks left")
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not any(k in g.blocks for k in auto),"cleared blocks are not rebuilt from the same evidence: "+str(list(g.blocks)))
check(any(b.get("source")=="manual" for b in g.blocks.values()),"manual block kept")
g.action("clear_suppressed",{})
g.poll_once(); g.poll_once()
check(any(k in g.blocks for k in auto),"after clearing 'Not re-blocked' they can come back")
# Rule ceiling covers everything SpamGuard writes, repeater blocks included (a spam wave must never
# flood openHop with rules)
m2=mock(); g2=guard(m2, max_total_rules=20); g2.apply_settings({"mode":"protect"})
for i in range(40):
    g2.action("block_hop",{"hop":f"{i+16:02X}"})
for i in range(60):
    m2.add(rname(),f"Different spam line number {i} with some filler text",["5A","2F"],ago=300-i)
g2.poll_once(); g2.last_sync=0; g2.sync_pending=True; g2.poll_once()
ours=[r for r in m2.policy["policy_engine"]["rules"] if r.get("name","").startswith("spamguard:")]
check(len(ours)<=20,"never more rules than the limit: "+str(len(ours)))
check(any(r.get("name")=="my own rule" for r in m2.policy["policy_engine"]["rules"]),"your own rule kept")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
