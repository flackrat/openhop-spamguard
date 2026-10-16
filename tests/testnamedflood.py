# A flood under real-looking first names with random tags ("Robin-cpg7u", "Olivier.rig.ae3f") sending short
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
flood=[("Robin-cpg7u","ꝁャ;Ÿづ␧Ч"),("Ralf188_29s64","%००»ŷ☎"),("Jelle-y3tfm","ᵐᦐ৺"),("Martijn627_d60jc","৺iи♡╟ŉŸ☰ĬŸ"),
       ("Bas-shed-1o0d","я☆ッ😇ם༄ᴋǴш░␧┛"),("Fastcat.oj5l","ᵀᵃ▸ภœ϶ ʋ⚙ɾ⁂·⊂ñ-♬"),("Olivier-h17a3","Ï┤╫☙ɛ"),("Olivier.rig.ae3f","ĔІブ"),
       ("Sanne-k4p9z","ԅ☼ᚦ∰"),("Daan_77_q1w8e","ʬ⌖ꙮ☍ᛃ")]
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
m.add("Hilltop Hiker","Morning all, clear skies up here",["A71C","2F0E"],ago=900)
for i,(n,t) in enumerate(flood):
    m.add(n,t,["C4D2",f"{0x10+i:02X}0A","2F0E"],ago=400-i*30)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
ev={e.sender:e for e in g.events}
check(sum(1 for n,_ in flood if ev.get(n) and ev[n].random)>=9,"flood names count as made-up: "+str([(n,ev[n].name_score,ev[n].garbage) for n,_ in flood if n in ev]))
check(any(b["kind"]=="hop" and b["value"]=="C4D2" for b in g.blocks.values()),"entry repeater blocked: "+str(list(g.blocks)))
check(m.decide("Joris-a8x2c","∯ᚱ☊",["C4D2","990A","2F0E"])=="drop","next flood message dropped")
check(m.decide("Hilltop Hiker","Anyone else seeing that junk?",["A71C","2F0E"])=="allow","genuine user elsewhere fine")
check(not ev["Hilltop Hiker"].random,"ordinary name not flagged")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
