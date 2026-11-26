# 6.55.0: narrowing spam sources. A sender heard by several repeaters is placed where all of them can hear it (the
# overlap of their hearing areas), measured on a made-up mesh where the truth is known; a first code no repeater
# using it has ever been next to is called made up instead of naming one; routes can be drawn; spam names that
# have advertised are shown as a clue. All places, keys and names are made up.
import sys, os, time, random, collections, statistics, logging
from harness import *
from mapworld import World, km
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
exec(open("testmapconfidence.py").read().split("def spam(")[0].split("logging.disable(logging.WARNING)")[1].split("ok=fail=0")[0])
exec("def guard_for"+open("testmapconfidence.py").read().split("def guard_for")[1].split("def spam(")[0])
def entries(g,paths,spammers=None):
    now=time.time(); g._rep_idx=None
    return g.spam_entries(now-86400,now-7*86400,{str(int(now//3600*3600)):{"p":dict(paths),"s":{}}},spammers or {},{})
res=[]; wide=[]; narrow=[]; moved=[]
for ws in (1,2,3):
    w=World(seed=ws); g=guard_for(w,ws); R=random.Random(70+ws)
    for t in range(25):
        while True:
            S=(R.uniform(38.8,41.4),R.uniform(-98.2,-93.6))
            near=[r for r in w.nearest(S,6) if km((r["lat"],r["lon"]),S)<=r["range"]]
            if len(near)>=3: break
        near=near[:3]; own="%02X"%(0x10+t)   # the spammer's own, unlisted first code
        paths=collections.Counter()
        for k in range(60):
            r=R.choice(near); paths[">".join([own]+w.path(r["i"]))]+=1
        ent=entries(g,paths)
        shown=[e for e in ent["entries"] if e["level"]!="guess"]
        if not shown: continue
        top=max(shown,key=lambda e:e["d7"]); d=km((top["lat"],top["lon"]),S)
        res.append(d<=top["radius_km"])
        if top.get("overlap"):
            wide.append(top["wide_km"]); narrow.append(top["radius_km"])
            moved.append((km(tuple(top["wide_at"]),S),d))
check(len(res)>=50,"most made-up spammers are placed (%d)"%len(res))
inside=sum(res)
check(inside>=0.9*len(res),"the sender is inside the shown area at least 90%% of the time (%d/%d)"%(inside,len(res)))
check(len(narrow)>=0.5*len(res),"the overlap is used for most places that several repeaters heard (%d of %d)"%(len(narrow),len(res)))
if narrow:
    print("median area radius: %d km before, %d km with the overlap"%(statistics.median(wide),statistics.median(narrow)))
    print("median distance from the sender: %.1f km from the middle, %.1f km from the overlap"%(statistics.median(m[0] for m in moved),statistics.median(m[1] for m in moved)))
    check(statistics.median(narrow)<=statistics.median(wide),"the area is never bigger")
    check(statistics.median(m[1] for m in moved)<statistics.median(m[0] for m in moved),"and its middle is closer to the sender")
# --- overlap maths on its own
g=guard_for(World(seed=1),1)
ov=g.overlap_area([(40.0,-95.0,30,10),(40.2,-95.0,30,10),(40.1,-94.8,30,10)])
check(ov and km((ov[0],ov[1]),(40.1,-94.93))<15 and ov[2]<30,"three overlapping circles give a smaller area between them: %s"%(ov,))
check(g.overlap_area([(40.0,-95.0,10,10),(41.0,-95.0,10,10)]) is None,"circles that don't meet give no overlap")
check(g.overlap_area([(40.0,-95.0,30,10)]) is None,"one repeater alone gives no overlap")
ov2=g.overlap_area([(40.0,-95.0,30,10),(40.2,-95.0,30,10),(40.1,-94.8,30,10),(41.5,-97.0,20,1)])
check(ov2 and ov2[2]<30,"a stray route or two doesn't spoil it")
# --- same-code check
g.adv_routes["B6AAAA01|63"]=[5,time.time(),40.0,-95.0,"Quarry North"]; g.adv_routes["B6BBBB02|27"]=[5,time.time(),40.5,-96.0,"Quarry South"]
g.adv_routes["CCCC0303|B6>04"]=[3,time.time(),40.1,-95.1,"Quarry East"]; g._adv_stamp+=1
cc=g.code_check("B6",["DD","93"]); check(cc["verdict"]=="made_up" and cc["same"]>=2,"a code no repeater using it has been next to is made up: %s"%cc)
cc=g.code_check("B6",["04"]); check(cc["verdict"]=="unlisted","a code seen passing adverts there, but from no known repeater, is unlisted")
cc=g.code_check("B6",["63"]); check(cc["verdict"]=="next" and cc["next_to"][0]["name"]=="Quarry North","a repeater really next to it is named")
# --- routes and advertised spam names
w=World(seed=2); g=guard_for(w,2)
r0=w.nearest((40.0,-95.5),1)[0]; p=["7Q"]+w.path(r0["i"])
pts=g.route_points(p); check(len(pts)>=2 and pts[-1][:2]==[round(g.me["lat"],4),round(g.me["lon"],4)],"a route is drawn to this repeater")
g.adv_routes["DEADBEEF|"+">".join(w.path(r0["i"]))]=[2,time.time(),40.01,-95.49,"Quarry Spammer"]; g._adv_stamp+=1
ent=entries(g,collections.Counter({">".join(p):30}),{"Quarry Spammer":{">".join(p):{str(int(time.time()//86400*86400)):30}}})
adv=ent["advertised"]; check(adv and adv[0]["name"]=="Quarry Spammer" and adv[0]["pts"],"a spam name that advertised is shown with its advert route")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
