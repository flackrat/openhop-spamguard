# A flood under real-looking first names with random tags ("Arno-q7k2d", "Wim.rig.c9d1") sending short
# unreadable text, through one entry repeater with 2-byte hashes (seen on a Dutch mesh). The names count as
# made-up and the text as unreadable, so the entry repeater gets blocked; ordinary names and short genuine
# messages are left alone. All names and messages are made up in the same style.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
flood=[("Arno-q7k2d","ꝁャ;Ÿづ␧Ч"),("Henk203_k81zt","%००»ŷ☎"),("Kees-p4m8v","ᵐᦐ৺"),("Pieter518_x41ra","৺iи♡╟ŉŸ☰ĬŸ"),
       ("Tom-shed-9k2w","я☆ッ😇ם༄ᴋǴш░␧┛"),("Quickfish.r7t2","ᵀᵃ▸ภœ϶ ʋ⚙ɾ⁂·⊂ñ-♬"),("Wim-k28d5","Ï┤╫☙ɛ"),("Wim.rig.c9d1","ĔІブ"),
       ("Lies-w3n6q","ԅ☼ᚦ∰"),("Gert_42_z8v3m","ʬ⌖ꙮ☍ᛃ")]
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
m.add("Hilltop Hiker","Morning all, clear skies up here",["A71C","2F0E"],ago=900)
for i,(n,t) in enumerate(flood):
    m.add(n,t,["C4D2",f"{0x10+i:02X}0A","2F0E"],ago=400-i*30)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
ev={e.sender:e for e in g.events}
check(sum(1 for n,_ in flood if ev.get(n) and ev[n].random)>=9,"flood names count as made-up: "+str([(n,ev[n].name_score,ev[n].garbage) for n,_ in flood if n in ev]))
check(any(b["kind"]=="hop" and b["value"]=="C4D2" for b in g.blocks.values()),"entry repeater blocked: "+str(list(g.blocks)))
check(m.decide("Huub-e5q7r","∯ᚱ☊",["C4D2","990A","2F0E"])=="drop","next flood message dropped")
check(m.decide("Hilltop Hiker","Anyone else seeing that junk?",["A71C","2F0E"])=="allow","genuine user elsewhere fine")
check(not ev["Hilltop Hiker"].random,"ordinary name not flagged")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
