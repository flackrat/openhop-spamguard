# The rule limit: however many blocks a spam wave creates, SpamGuard never writes more than max_total_rules,
# and its standing rules (wardriving, FloodGuard and the known-people rule FloodGuard relies on) are never
# the ones left out. All data made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m, max_total_rules=20, wardrive_block=True)
g.fg.update(ready=time.time(), limit=12, since=time.time(), last_step=time.time())
now=time.time()
for i in range(40):   # a heavy wave: lots of text blocks and identity-changing repeater blocks
    g._add_block(f"text:{i}", "text", f"buy cheap mesh upgrades now number {i:03d}", "test", "campaign", ttl=3600)
for i in range(10):
    g._add_block(f"suffix:{i}", "suffix", [f"{i:02X}", "2F"], "test", "rotation", ttl=3600)
    g.blocks[f"suffix:{i}"]["allow_ids"]={}
main, tail = g.build_rule_sets()
allr=main+tail; names=[r["name"] for r in allr]
check(len(allr)<=20, f"never more than the limit: {len(allr)}")
check(any("wardriving" in n for n in names),"the wardriving rule is kept")
check(sum("floodguard" in n for n in names)==3,"all FloodGuard rules are kept (limit, unscoped, adverts)")
ki=[i for i,r in enumerate(tail) if "known-people" in r["name"]]; fi=[i for i,r in enumerate(tail) if "flood-limit" in r["name"]]
check(ki and fi and ki[0]<fi[0],"with the known-people rule before them")
check(any("text:" in n for n in names),"and the blocks share what's left")
g2=guard(mock(), max_total_rules=20, wardrive_block=False, floodguard=False)
for i in range(40):
    g2._add_block(f"text:{i}", "text", f"buy cheap mesh upgrades now number {i:03d}", "test", "campaign", ttl=3600)
m2,t2=g2.build_rule_sets()
check(len(m2+t2)==20,"without standing rules the blocks get the whole limit")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
