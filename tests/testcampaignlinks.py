# How campaigns link up: groups with reasons, strong and weak told apart, a group set aside for a week, and
# nothing ever held or blocked by it. Made-up names, texts and repeaters.
import sys, time, collections, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
class Ev:
    def __init__(s,sender,text): s.sender=sender; s.text=text
def camp(text,names,hops):
    return {"senders":set(names),"events":[Ev(n,f"{text} {i}") for i,n in enumerate(names)],"hops":collections.Counter(hops)}
g=guard(mock())
C={"a":camp("Free quarry gravel at qgravel.example",["Kip One","Kip Two","Pat Three"],{"7D":3}),
   "b":camp("Cheap ridge radios at qradio.example",["Kip One","Kip Two","Zed Four"],{"7D":2,"A7":1}),   # shares two names: strong
   "c":camp("Lucky draw tonight at qdraw.example",["Lo Five","Lo Six"],{"C4":2}),
   "d":camp("Lucky prize tonight at qprize.example",["Lo Seven","Lo Eight"],{"C4":2}),               # same repeater only: weak
   "e":camp("Something else entirely here",["Solo Nine"],{"2F":1})}
before=json.dumps(sorted(g.blocks))
L=g.campaign_links(C)
check(len(L)==2,"two groups: %s"%[ [c["example"][:12] for c in x["campaigns"]] for x in L])
st=[x for x in L if x["strong"]]; wk=[x for x in L if not x["strong"]]
check(len(st)==1 and any("2 names sent both" in r["text"] for r in st[0]["reasons"]),"shared names: strongly linked")
check(len(wk)==1 and any("came in through C4" in r["text"] and not r["strong"] for r in wk[0]["reasons"]),"only the same repeater: possibly related")
check(L[0]["strong"],"strong groups first")
check(not any("Something else" in c["example"] for x in L for c in x["campaigns"]),"an unrelated campaign stays out")
# names that took over each other's repeats link two campaigns strongly
g.name_links={"Lo Five":{"after":["Lo Seven"],"ts":time.time()}}
L2=g.campaign_links(C); w=[x for x in L2 if any("Lo" in n for n in x["names"])][0]
check(w["strong"] and any("took over" in r["text"] for r in w["reasons"]),"took over each other's repeats: strong")
# set aside for a week
r=g.action("dismiss_link",{"id":L2[0]["id"]})
check(all(x["id"]!=L2[0]["id"] for x in g.campaign_links(C)),"a group set aside isn't shown")
check(json.dumps(sorted(g.blocks))==before,"nothing is held or blocked by the view")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg, state_file=g.cfg["state_file"]))
check(L2[0]["id"] in g2.links_dismissed,"set aside survives a restart")
g.action("dismiss_link",{"id":L2[0]["id"],"undo":1})
check(any(x["id"]==L2[0]["id"] for x in g.campaign_links(C)),"undo shows the group again")
check(g.campaign_links({})==[],"no campaigns: nothing")
try: g.action("dismiss_link",{"id":"../../x"}); check(False,"a bad id is refused")
except Exception: check(True,"a bad id is refused")
# a strong pair never lends its confidence to a campaign joined only by a weak link (A-B strong, B-C weak)
g.name_links={}
M={"a":camp("Quarry deals at qdeal.example",["Ash One","Ash Two","Ash Three"],{"9D":3}),
   "b":camp("Quarry offers at qoffer.example",["Ash One","Ash Two"],{"E1":3}),          # shares two names with a: strong
   "c":camp("Spare parts at qparts.example",["Bo One","Bo Two","Bo Three"],{"E1":3})}   # only the same repeater as b: weak
L3=g.campaign_links(M)
st=[x for x in L3 if x["strong"]]; wk=[x for x in L3 if not x["strong"]]
ex=lambda x: sorted(c["example"].split(" at ")[0] for c in x["campaigns"])
check(len(st)==1 and ex(st[0])==["Quarry deals","Quarry offers"],"the strong group holds only the strongly linked pair: %s"%[ex(x) for x in st])
check(len(wk)==1 and "Spare parts" in ex(wk[0]),"the weakly joined campaign is shown on its own, as possibly related")
check(all(not r["strong"] for r in wk[0]["reasons"]),"a possibly related link lists only its weak reason: %s"%wk[0]["reasons"])
check(not any(r["text"].startswith("2 names") for r in wk[0]["reasons"]),"the strong pair's reason isn't borrowed")
# two strong groups joined by one weak link: both stay strong, plus one possibly related entry
P={"a":camp("One at q1.example",["Di A","Di B"],{"1A":2}),"b":camp("Two at q2.example",["Di A","Di B"],{"2B":2}),
   "c":camp("Three at q3.example",["Ed A","Ed B"],{"2B":2}),"d":camp("Four at q4.example",["Ed A","Ed B"],{"4D":2})}
L5=g.campaign_links(P)
check(sum(x["strong"] for x in L5)==2 and sum(not x["strong"] for x in L5)==1,"two strong groups and one possibly related link: %s"%[(ex(x),x["strong"]) for x in L5])
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
