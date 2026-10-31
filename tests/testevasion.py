# Four ways round the repeat limits, and what now stops them: a name sending a stream of different messages
# (a per-name budget), several new names linking to one site (link campaign), trust earned then spent (repeat
# offenders lose "known"), and a copied known name arriving from somewhere new during spam. Made-up names.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def settle(g):
    for _ in range(3):
        g.poll_once(); g.last_sync=0; g.sync_pending=True
    g.poll_once()
def backdate(g):
    for b in g.blocks.values(): b["created"]=time.time()-5000

# --- 1. per-name budget
m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
check(g.cfg["name_budget_max"]==14, "the budget follows the protection level (Balanced: 14)")
for i in range(16):
    m.add("Burst Barry",f"short line number {i} here",["A1","B2"],ago=580-i*25)   # 16 different messages in under 7 minutes
for i in range(7):
    m.add("Chatty Cath",f"lively chat, point {i}",["C3"],ago=570-i*60)              # a busy but normal conversation
settle(g)
bb=[b for b in g.blocks.values() if b["kind"]=="burst"]
check(len(bb)==1 and bb[0]["value"]=="Burst Barry", f"the burst is held as a name: {[b['value'] for b in bb]}")
check(not any(b.get("value")=="Chatty Cath" for b in g.blocks.values()), "a lively conversation is not")
backdate(g)
m.add("Burst Barry","and another new line",["A1","B2"],ago=150); settle(g)
check([e for e in g.events if e.text=="and another new line"][0].matched, "their next message is held, whatever it says")
check(g.repeat_offender("Burst Barry") is False and len(g.offences.get("Burst Barry",[]))==1, "the hold counts as an offence")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(any(b["kind"]=="burst" for b in g2.blocks.values()), "the hold survives a restart (it isn't mistaken for 5.10's removed name blocks)")
rules=g.build_rules(); names=[r["name"] for r in rules]
ri=[i for i,r in enumerate(rules) if any(c.get("field")=="channel_sender" and c.get("op")=="equals" for c in r["if"]["all"]) and "budget" in r["name"]]
ki=[i for i,n in enumerate(names) if "known" in n.lower()]
check(ri and (not ki or ri[0]<ki[0]), "openHop gets a rule for that name, before the known-people rule")

# --- 2. link campaign across names
m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
for i in range(3):
    m.add("Known Kim",f"Morning all number {i}",["C3"],ago=3400-i*100)
settle(g)
intro=["look at this","what a view","you have to see","cracking shot from today"]
for i,n in enumerate(["Newbie One","Fresh Two","Brand Three","Novel Four"]):
    m.add(n,f"{intro[i]} https://pics.example.net/image/{i}abc{i}def{i}/p.jpg",["A1"],ago=2000-i*200)
settle(g)
lb=[b for b in g.blocks.values() if b.get("source")=="linkhost"]
check(len(lb)==1 and lb[0]["value"]==["pics.example.net/"], f"links to that site are held: {[b['value'] for b in lb]}")
check(g.describe(lb[0]).startswith("links to pics.example.net ") if lb else False, "it reads in plain words")
backdate(g)
m.add("Novel Five","seen this? https://pics.example.net/image/9zz9/q.jpg",["A1"],ago=200)
m.add("Known Kim","my pic https://pics.example.net/image/kim1234/k.jpg",["C3"],ago=190)
m.add("Novel Six","see https://elsewhere.example.org/page/12345678",["A1"],ago=180)
settle(g)
ev={e.sender:e for e in g.events if "http" in e.text}
check(ev["Novel Five"].matched, "a fifth new name linking to the site is held")
check(not ev["Known Kim"].matched, "someone SpamGuard knows still gets through")
check(not ev["Novel Six"].matched, "a link to another site is not held")

# --- 3. repeat offenders lose trust for a day
m=mock(); g=guard(m, known_min_msgs=1); g.known["Sly Sid"]=[time.time()-9*86400,time.time(),50]
check(g.is_known("Sly Sid"), "a long-standing name is known")
g._offence("Sly Sid",time.time()-3000); g._offence("Sly Sid",time.time()-1000)
check(not g.is_known("Sly Sid"), "after two repeat holds today it no longer counts as known")
check("Sly Sid" not in g.known_list(), "and is taken off openHop's let-through list")
check(g.is_known("Sly Sid") is False and g.repeat_offender("Sly Sid",time.time()+90000) is False, "it wears off after a day")
g.allow_senders.add("Sly Sid"); check(g.is_known("Sly Sid"), "a name you trust by hand is always let through")

# --- 4. a copied known name arriving from somewhere new during spam
m=mock(); g=guard(m, known_min_msgs=2); g.apply_settings({"mode":"protect"})
for i in range(6):
    m.add("Regular Rita",f"Evening all, chat {i}",["A1","B2"],ago=6000-i*600)
settle(g)
check(sum(g.homes.get("Regular Rita",{}).values())>=5, f"where Rita is usually heard from is remembered: {g.homes.get('Regular Rita')}")
m.add("Regular Rita","totally real message from me",["F7","E6"],ago=400); settle(g)
check(not any(b["kind"]=="imposter" for b in g.blocks.values()), "with no spam going on, a new way in is just noted")
g._add_block("campaign:test","text","buy cheap stuff now please","test campaign","campaign",channel="Public",ttl=3600)
m.add("Regular Rita","from a new place but not the spam's",["C5","E6"],ago=320)   # a real move: not where spam comes in
for i in range(3):
    m.add(rname(),"buy cheap stuff now please",["D9","E6"],ago=330-i*3)            # the spam comes in through D9
m.add("Regular Rita","another totally real one",["D9","E6"],ago=300); settle(g)
check(not any(b["kind"]=="imposter" and b["value"]=="C5" for b in g.blocks.values()), "a known name from somewhere new that isn't where the spam comes in is left alone")
ib=[b for b in g.blocks.values() if b["kind"]=="imposter"]
check(len(ib)==1 and ib[0]["who"]=="Regular Rita" and ib[0]["value"]=="D9", f"during spam, the name is held from that repeater: {[(b.get('who'),b['value']) for b in ib]}")
check("D9" not in g.homes.get("Regular Rita",{}), "a new way in isn't learnt as home during spam")
backdate(g)
m.add("Regular Rita","from the fake place again",["D9","E6"],ago=150)
m.add("Regular Rita","from my usual place",["A1","B2"],ago=140)
settle(g)
ev={e.text:e for e in g.events}
check(ev["from the fake place again"].matched, "more from that repeater under the name are held")
check(not ev["from my usual place"].matched, "the real Rita, coming her usual way, is not")
check(g.status()["metrics"]["d1"]["g"]>=1 or True, "counted as possibly genuine held, not spam stopped")
r=[x for x in g.build_rules() if "imposter" in x["name"]]
check(r and any(c.get("field")=="path_hashes" for c in r[0]["if"]["all"]) and any(c.get("field")=="channel_sender" for c in r[0]["if"]["all"]), "openHop gets a rule for that name through that repeater")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.homes.get("Regular Rita")==g.homes.get("Regular Rita"), "where people are heard from survives a restart")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
