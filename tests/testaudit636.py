# Narrower holds and one more disguise caught. Made-up names, messages and repeater codes.
import sys, logging, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
FAST=dict(floodguard=False,known_min_msgs=3,known_min_minutes=60,vary_limits=False)

# A flood under a known person's name through a repeater they use: held there only, not everywhere, no mark against them
m=mock(); g=guard(m,**FAST)
for i in range(10): m.add("Ann Hill",f"{words[i%11]} {words[(i*3)%11]} chat {i}",["4C"] if i%2 else ["5E","4C"],ago=7000-i*600)
g.apply_settings({"mode":"protect"}); sync(g)
check(g.is_known("Ann Hill"),"Ann is known")
for i in range(int(g.cfg["name_budget_max"])+6): m.add("Ann Hill",f"flood line {i} {words[i%11]} {words[(i*7)%11]}",["4C","77"])
sync(g); sync(g)
bl=[b for b in g.blocks.values() if b.get("source")=="budget"]
check(bl and all(b["kind"]=="imposter" and b["value"]=="4C" for b in bl),"the hold is on her name through that repeater only: "+str([(b["kind"],b["value"]) for b in bl]))
check(not any(b["kind"]=="burst" and b["value"]=="Ann Hill" for b in g.blocks.values()),"her name is not held everywhere")
check(not g.repeat_offender("Ann Hill"),"and it isn't counted against her")
e=sg.Event(ts=time.time(),sender="Ann Hill",text="hello from the other way in",path=["5E","9B"],channel="Public")
check(not any(g.block_matches(b,e) for b in g.blocks.values()),"she still gets through another way")

# An unknown name flooding is held as before
m2=mock(); g2=guard(m2,**FAST); g2.apply_settings({"mode":"protect"})
for i in range(int(g2.cfg["name_budget_max"])+6): m2.add("Zed Quill",f"flood line {i} {words[i%11]} {words[(i*7)%11]}",["A1","B2"])
sync(g2); sync(g2)
check(any(b["kind"]=="burst" and b["value"]=="Zed Quill" for b in g2.blocks.values()),"an unknown name flooding is still held")

# The same message with punctuation dropped inside its words, from several ordinary-looking names
m3=mock(); g3=guard(m3,**FAST); g3.apply_settings({"mode":"protect"})
base="please visit the amazing widget shop for cheap prices today"
names=["Kim Lane","Lou Park","Max Dale","Ned Ford","Oli West","Pat Gale"]
for i,n in enumerate(names):
    ws=base.split(); j=i%len(ws); ws[j]=ws[j][:2]+".,-!;:"[i]+ws[j][2:]
    m3.add(n," ".join(ws),["A1","B2"] if i%2 else ["C3","D4"]); sync(g3)
check("lockdown" in g3.blocks or any(b.get("source")=="campaign" for b in g3.blocks.values()),"copies split by punctuation inside words are acted on: "+str([(b["kind"],b.get("source")) for b in g3.blocks.values()]))

# After you remove an automatic block on a repeater, it isn't put back, but the spam's route is held
m4=mock(); g4=guard(m4,**FAST); g4.apply_settings({"mode":"protect"})
for i in range(10): m4.add(rname(),f"{words[i%11]} hello {rname(4)} {i}",["A1","B2"])
sync(g4); sync(g4)
if "hop:A1" in g4.blocks:
    g4.action("unblock",{"key":"hop:A1"})
    for i in range(6): m4.add(rname(),f"{words[i%11]} again {rname(4)} {i}",["A1","B2"])
    sync(g4); sync(g4)
    check("hop:A1" not in g4.blocks,"the block you removed is not put back")
    check(any(b["kind"]=="route" and b["value"]==["A1","B2"] for b in g4.blocks.values()),"the route the spam uses is held instead: "+str(list(g4.blocks)))
else:
    check(False,"expected a repeater block to start with: "+str(list(g4.blocks)))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
