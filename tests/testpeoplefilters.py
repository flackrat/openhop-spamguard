# People: filters for names worth a look, names heard from a new direction, names you marked, and an order with the
# most likely spam first. Counts match the rows. All names and repeater codes are made up.
import logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time()
m=mock(); g=guard(m, floodguard=False, spoof_watch=True)
for i,n in enumerate(["Quarry Pete","Canal Boat Ted","Hilltop Mo","Lock Keeper Q","Visitor Q7"]):
    g.known[n]=[now-9*86400, now-60*(i+1), 20]
# a probable copy (red) of one name, a new direction (amber) only for another
g.dirs[g.name_family("Quarry Pete")]={"who":"Quarry Pete","h":{},"all":{},"p":{},"n":30,"last":now,"pend":{},"bad":[],"auto":[],"dd":[1,2],
    "copies":[[now-3600,"3E>5D","red",["device"]]]}
g.dirs[g.name_family("Canal Boat Ted")]={"who":"Canal Boat Ted","h":{},"all":{},"p":{},"n":30,"last":now,"pend":{},"bad":[],"auto":[],"dd":[1,2],
    "copies":[[now-3600,"7A>2B","amber",["new"]]]}
g.dirs[g.name_family("Lock Keeper Q")]={"who":"Lock Keeper Q","h":{},"all":{},"p":{},"n":30,"last":now,"pend":{},"bad":[],"auto":[],"dd":[1,2],
    "copies":[[now-9*86400,"7A>2B","amber",["new"]]]}   # a week ago: no longer shown
# your marks: spam on one, both ways on another
g.mark_counts["Visitor Q7"]=[3,0,now]
g.mark_counts["Hilltop Mo"]=[1,2,now]
P=lambda **b: g.people(b)
d=P(show="all")
c=d["counts"]
check(c["copied"]==1 and c["check"]==1,"one probable copy, one name to check (the copy isn't counted twice, the old one has aged out): %s"%{k:c[k] for k in ("copied","check")})
check(c["marked"]==2 and c["mixed"]==1,"two marked as spam, one of them both ways")
check([r["name"] for r in P(show="check")["rows"]]==["Canal Boat Ted"],"Check the route lists the amber one")
check([r["name"] for r in P(show="copied")["rows"]]==["Quarry Pete"],"Name copied lists the red one")
check(sorted(r["name"] for r in P(show="marked")["rows"])==["Hilltop Mo","Visitor Q7"],"Marked spam by you")
check([r["name"] for r in P(show="mixed")["rows"]]==["Hilltop Mo"],"Marked both ways")
w=P(show="worth")["rows"]
check([r["name"] for r in w]==["Visitor Q7"] and all(r["warmth"]["level"] in ("amber","red") for r in w),"Worth a look: the hot end of the bar only: %s"%[(r["name"],r["warmth"]) for r in w])
for k in ("copied","check","marked","mixed","worth","active","all"):
    check(P(show=k,limit=100)["total"]==c[k],f"the {k} count matches its rows")
o=[r["warmth"]["score"] for r in P(show="all",sort="warmth",limit=100)["rows"]]
check(o==sorted(o,reverse=True) and P(show="all",sort="warmth")["rows"][0]["name"]=="Visitor Q7","Most likely spam first: hottest at the top: %s"%o)
check(P(show="all",sort="nonsense")["sort"]=="recent" and P(show="nonsense")["show"]=="active","anything else falls back safely")
# search still narrows every count
check(P(show="all",q="ted")["counts"]["check"]==1 and P(show="all",q="pete")["counts"]["check"]==0,"search narrows the counts too")
# with lots of names it stays quick
for i in range(800): g.known[f"Walker Q{i:03d}"]=[now-5*86400, now-i, 5]
t=time.time(); P(show="worth",sort="warmth"); took=time.time()-t
check(took<1.5,"800 names sorted by likely spam in %.2fs"%took)
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
