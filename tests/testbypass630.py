# 6.30.0: ways round SpamGuard found in a private review, each closed. Text hidden in @[...] brackets is read;
# a flood under a copied name doesn't teach SpamGuard a new usual way in; a copied well-known name sending
# spam-shaped text is caught at calm times too; "?" names count towards "far too many"; automatic lockdowns
# can't be retriggered all day; a repeater many known people use needs two signs; an allowed phrase only
# covers messages that are mostly that phrase. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
def kinds(g): return {(b["kind"],b.get("source")) for b in g.blocks.values()}

# 1. Text smuggled inside @[...] is read like any other text
check(sg.smuggled("@[This repeater network is run by frauds] @[see the truth now]"),"smuggled text spotted")
check(not sg.smuggled("@[Mobile - MC - V4] thanks, heard you 5 by 9") and not sg.smuggled("@[Dave] hi"),"ordinary replies are not")
check("frauds" in sg.normalise("@[This repeater network is run by frauds] @[see the truth now]"),"normalised text keeps it")
check(sg.normalise("@[Dave M7ABC] good morning all")=="good morning all","a real mention is still left out")
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
for i,n in enumerate(["Dave Smith","Paul Jones","Mike Brown","Tony Green","Steve White"]):
    m.add(n,"@[This repeater network is run by frauds] @[see the truth now]",[["4C"],["2F"],["7A"],["5B"],["1D"]][i],ago=300-i*30); sync(g)
check(any(b["kind"]=="text" for b in g.blocks.values()),"copies of smuggled text build a text block")

# 2. A flood under a copied name doesn't become that person's usual way in
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
for i in range(6): m.add("Ann Hill",f"Morning all, chat {i}",["4C","2F"],ago=7200-i*600)
g.apply_settings({"mode":"protect"}); sync(g)
for i in range(16): m.add("Ann Hill",f"buy cheap stuff number {i} now",["9A","77"],ago=500-i*20)
sync(g)
check("9A" not in g.homes.get("Ann Hill",{}),"the flood's repeater is not learnt as her usual way in")
for i in range(4): m.add("Ann Hill","this exact line again and again",["9A","77"],ago=60-i*5)
sync(g)
check(not g.offences.get("Ann Hill") and g.is_known("Ann Hill"),"repeats from the same place later still aren't counted against her")

# 3. A copied well-known name sending spam-shaped text at a calm time
m=mock(); g=guard(m,floodguard=False,known_min_msgs=3,known_min_minutes=60)
words=["morning","weather","antenna","coffee","radio","garden","football","traffic","lunch","repeater","solar"]
for i in range(22): m.add("Ann Hill",f"{words[i%11]} {words[(i*3)%11]} talk {i}",["4C","2F"],ago=6600-i*290)
g.apply_settings({"mode":"protect"}); sync(g)
check(not g.attack_on(time.time()),"no attack under way")
m.add("Ann Hill","everyone go to http://example.invalid/free now",["9A","77"],ago=0); sync(g)
check(any(b["kind"]=="imposter" and b["value"]=="9A" for b in g.blocks.values()),"her name is held from the new repeater")
m.add("Ann Hill","see you all at the meet on Saturday",["6E","77"],ago=0); sync(g)
check(not any(b["kind"]=="imposter" and b["value"]=="6E" for b in g.blocks.values()),"an ordinary message from a new place is left alone")

# 4. A name of "?" counts towards far too many messages
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
for i in range(16): m.add("?",f"random noise {i} {i*7}",["4C"],ago=500-i*20)
sync(g)
check(any(b["kind"]=="burst" and b["value"]=="?" for b in g.blocks.values()),"held for sending far too many")

# 5. Automatic lockdowns can't be retriggered all day
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"}); sync(g)
hops=["11","22","33","44","55","66","77"]
def flood():
    for i in range(14): m.add(rname(),f"{rname()} {rname()}",[hops[i%7],"4C"],ago=10)
    sync(g)
flood(); check("lockdown" in g.blocks,"first lockdown")
g.blocks.pop("lockdown"); flood(); check("lockdown" in g.blocks,"second lockdown")
g.blocks.pop("lockdown"); flood()
check("lockdown" not in g.blocks and g.suppressed.get("lockdown",0)>time.time()+3600,"no third within the hour; paused for two hours")
check(any("third automatic lockdown" in a["msg"] for a in g.activity),"you are told")

# 6. A repeater many known people use needs two signs
m=mock(); g=guard(m,floodguard=False,hop_prefer_route=False)
for p in range(6):
    for i in range(4): m.add(f"Regular {p}",f"hello from regular {p}, number {i}",["4C"],ago=5000-i*300)
g.apply_settings({"mode":"protect"}); sync(g)
check(g._busy_home("4C") and not g._busy_home("9A"),"4C is a busy usual way in")
for i in range(4): m.add(rname(),f"made up {rname()}",["4C"],ago=60-i)
sync(g)
check("hop:4C" not in g.blocks,"one sign doesn't block it")
check(any("usual way in for many" in a["msg"] for a in g.activity),"you are told why")

# 7. An allowed phrase only covers messages that are mostly that phrase
m=mock(); g=guard(m,floodguard=False); g.allow_texts.add("net tonight")
check(g.text_allowed("Net tonight at 8!"),"short message with the phrase is allowed")
check(not g.text_allowed("net tonight - everyone go to the fake site and buy the stuff, the real developers are frauds"),
      "spam wrapped round the phrase is not")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
