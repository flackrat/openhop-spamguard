# One name sends the same reply over and over, each copy ending in a different made-up code so that no two are
# identical. The repeat limits count them as one template, hold the later ones, and leave everything else the
# name says (and other people's messages) alone. All names, codes and messages are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def tmpl(t): return sg.random_tail_template(t)
check(tmpl("@[Sam-N0CALL]🤡\nrynx95jx") is not None, "a mention, an emoji and a made-up code is a template")
check(tmpl("@[Sam-N0CALL]🤡\nrynx95jx")[0]==tmpl("@[Sam-N0CALL]🤡\ne8rtb15y")[0], "two codes give one template")
check(tmpl("@[Sam-N0CALL]🤡\nrynx95jx")[0]!=tmpl("@[Sam-N0CALL]⚠️\nrynx95jx")[0], "a different emoji is a different template")
check(tmpl("@[Sam-N0CALL] you still here")is None, "ordinary words are not a template")
check(tmpl("@[Sam] https://img.example/image/9a8b7c6d5e4f")is None, "a code inside a link is not")
check(tmpl("@[Sam 7f24f3a1] hello there")is None, "a code inside a mention is not")
check(tmpl("Go 2fa4b9c1d now")is None, "too little text before the code")

m=mock(); g=guard(m, known_min_msgs=2, slow_repeat_max=2); g.apply_settings({"mode":"protect"})
for i in range(3):
    m.add("Sam Troll",f"Hello from the hill number {i}",["A1","B2"],ago=3000-i*100)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Sam Troll"), "the sender is a known name")
codes=["rynx95jx","e8rtb15y","rvdek7nz","txvvd5sd","vsj5r6v1","k2m9x4qa"]
for i,cd in enumerate(codes[:3]):
    m.add("Sam Troll",f"@[Pat-Radio]🤡\n{cd}",["A1","B2"],ago=1500-i*200)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for b in g.blocks.values(): b["created"]=time.time()-1000     # as if made while the sends were happening
for i,cd in enumerate(codes[3:]):
    m.add("Sam Troll",f"@[Pat-Radio]🤡\n{cd}",["A1","B2"],ago=420-i*60)
m.add("Sam Troll","@[Pat-Radio] you still here",["A1","B2"],ago=200)
m.add("Other Person","@[Pat-Radio]🤡\nzz11yy22xx",["C3"],ago=190)
m.add("Other Person","@[Pat-Radio] morning",["C3"],ago=180)
for _ in range(3):
    g.poll_once(); g.last_sync=0; g.sync_pending=True
g.poll_once()
bl=[b for b in g.blocks.values() if b["kind"]=="repeat"]
check(len(bl)==1, f"one repeat block was made: {[(b['value'],b['reason']) for b in bl]}")
if bl:
    b=bl[0]
    check(b["who"]=="Sam Troll" and b["value"]=="@[Pat-Radio]🤡", f"it holds that name's copies: {b['value']!r}")
    check("different made-up code" in b["reason"], "the reason says why: "+b["reason"])
    check("Sam Troll" in g.describe(b), "it reads in plain words: "+g.describe(b))
evs={e.text:e for e in g.events}
stopped=[e for e in g.events if e.sender=="Sam Troll" and e.matched]
check(len(stopped)>=1, f"later copies are held: {len(stopped)}")
check(not any(e.matched for e in g.events if e.sender=="Other Person"), "another person using the same words is untouched")
check(not any(e.matched for e in g.events if e.text=="@[Pat-Radio] you still here"), "their ordinary reply is untouched")
# the rule openHop is given
rules=[r for r in g.build_rules() if "repeat" in r["name"].lower() or "repeats" in r["name"].lower()] if hasattr(g,"build_rules") else []
# survives a restart
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(any(k.rsplit("|",2)[-1].startswith("T") for k in g2.slow_sends), "the count survives a restart")

# --- the same link again and again, with different words round it
check(sg.first_link("Great view from the top!! https://img.example.net/image/9a8b7c6d5e4f3a2b/pic.jpg…")=="img.example.net/image/9a8b7c6d5e4f3a2b/pic.jpg", "the link is picked out")
check(sg.first_link("see https://a.io/x")is None, "a very short link is too little to go on")
check(sg.first_link("no link here at all")is None, "no link, nothing to count")
m=mock(); g=guard(m, known_min_msgs=2, slow_repeat_max=2); g.apply_settings({"mode":"protect"})
URL="https://img.example.net/image/9a8b7c6d5e4f3a2b/pic.jpg"
words=["Lovely view","Really lovely","Lovely view!!","Thanks for looking","Lovely again"]
for i in range(3):
    m.add("Lee Linker",f"Hello from the hill number {i}",["A1","B2"],ago=3000-i*100)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for i,w in enumerate(words[:3]):
    m.add("Lee Linker",f"{w} {URL}",["A1","B2"],ago=1500-i*300)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for b in g.blocks.values(): b["created"]=time.time()-1000
for i,w in enumerate(words[3:]):
    m.add("Lee Linker",f"{w} {URL}",["A1","B2"],ago=400-i*60)
m.add("Lee Linker","A different link https://other.example.org/page/abcdef123456",["A1","B2"],ago=250)
m.add("Other Person",f"Did you see this {URL}",["C3"],ago=240)
for _ in range(3):
    g.poll_once(); g.last_sync=0; g.sync_pending=True
g.poll_once()
lb=[b for b in g.blocks.values() if b["kind"]=="repeat" and "link" in (b.get("reason") or "")]
check(len(lb)==1 and lb[0]["who"]=="Lee Linker", f"one block for the link, against that name: {[(b['value'],b['reason']) for b in lb]}")
check(sum(1 for e in g.events if e.sender=="Lee Linker" and e.matched)>=2, "later copies of the link are held, however worded")
check(not any(e.matched for e in g.events if e.sender=="Other Person"), "someone else sharing the same link is untouched")
check(not any(e.matched for e in g.events if e.text.startswith("A different link")), "a different link from the same name is untouched")

# --- a name already held for repeating is treated more strictly
m=mock(); g=guard(m, known_min_msgs=2, slow_repeat_max=3); g.apply_settings({"mode":"protect"})
now0=time.time()
check(not g.repeat_offender("Lee Linker"), "nobody starts as an offender")
g._offence("Lee Linker", now0-3600); check(not g.repeat_offender("Lee Linker"), "one hold isn't enough")
g._offence("Lee Linker", now0-1800); check(g.repeat_offender("Lee Linker"), "two holds in a day makes a repeat offender")
check(not g.repeat_offender("Lee Linker", now0+2*86400), "and it wears off after a day")
for i in range(3):
    m.add("Lee Linker",f"Hello from the hill number {i}",["A1","B2"],ago=3000-i*100)
    m.add("Pat Regular",f"Morning all, number {i}",["C3"],ago=2950-i*100)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
U2="https://img.example.net/image/aaaa1111bbbb2222/pic.jpg"
for i in range(3):   # three sends: not over the usual limit of 3, but over the stricter 2
    m.add("Lee Linker",f"{words[i]} {U2}",["A1","B2"],ago=1500-i*300)
    m.add("Pat Regular",f"Have you seen this {U2}",["C3"],ago=1490-i*300)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(any(b["kind"]=="repeat" and b.get("who")=="Lee Linker" for b in g.blocks.values()), "the offender is held after one fewer copy")
check(not any(b.get("who")=="Pat Regular" for b in g.blocks.values()), "a name with no history is held at the usual number, not the stricter one")
hb=[b for b in g.blocks.values() if b.get("value")=="img.example.net/"]
check(len(hb)==1 and hb[0]["who"]=="Lee Linker", f"their links to that site are held too: {[(b['value'],b['reason']) for b in hb]}")
for b in g.blocks.values(): b["created"]=time.time()-1000
m.add("Lee Linker","New picture https://img.example.net/image/cccc3333dddd4444/new.jpg",["A1","B2"],ago=120)
m.add("Lee Linker","Plain chat, no link",["A1","B2"],ago=110)
m.add("Pat Regular","New picture https://img.example.net/image/cccc3333dddd4444/new.jpg",["C3"],ago=100)
g.poll_once()
ev={e.text[:12]+e.sender:e for e in g.events}
check(ev["New picture Lee Linker"].matched, "a brand-new link on that site from the offender is held at once")
check(not ev["Plain chat, Lee Linker"].matched, "their plain chat is not")
check(not ev["New picture Pat Regular"].matched, "someone else posting the same site is not")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.repeat_offender("Lee Linker"), "being an offender survives a restart")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
