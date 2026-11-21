# 6.45.0: how sure the spam map is, checked against a made-up mesh where the truth is known. A first repeater is
# only "certain" when the repeater after it confirms it, each place carries the area the sender can be in, routes
# with a made-up start are never pinned confidently on an innocent repeater, copies of a name are placed, and
# repeater adverts are kept in the evidence log so a replay can rebuild the map. All places and names are made up.
import sys, os, json, tempfile, time, random, math, collections, statistics, logging
from harness import *
from mapworld import World, km
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def guard_for(w, seed):
    st=os.path.join(tempfile.mkdtemp(prefix="sgtest-map-"),"state.json")
    g=sg.SpamGuard({"mode":"monitor","state_file":st,"evidence_log":False,"map_directory":True})
    g._save_state=lambda *a,**k:None
    g.me={"name":"Me","lat":w.me["lat"],"lon":w.me["lon"],"hash":"00"}
    R=random.Random(seed); now=time.time(); listed=[]
    for r in w.reps:
        if r["i"] in w.dist and R.random()<0.6 and w.dist[r["i"]][0]<=11:
            p=w.path(w.prev[r["i"]]) if w.prev[r["i"]] is not None else []
            g.adv_routes[r["key"]+"|"+">".join(p)]=[R.randint(2,20),now-R.uniform(0,5*86400),r["lat"],r["lon"],r["name"]]
            listed.append({"key":r["key"],"name":r["name"],"seen":now-3600,"lat":r["lat"],"lon":r["lon"]})
    g.repeaters={"ts":now,"list":listed}
    g.public_reps={"ts":now,"list":[{"key":r["key"],"name":r["name"],"lat":r["lat"],"lon":r["lon"],"seen":now-86400,"src":"map"} for r in w.reps],"error":None}
    g._rep_idx=None
    while g.learn_step(rest_s=0): pass
    return g

def spam(w,R,kind):
    while True:
        S=(R.uniform(38.8,41.4),R.uniform(-98.2,-93.6)); near=w.nearest(S,1)[0]
        if km((near["lat"],near["lon"]),S)<20: break
    base=w.path(near["i"]); paths=collections.Counter()
    for k in range(R.randint(20,60)):
        p=list(base)
        if kind in ("own","own_forged"): p=["%02X"%(0x10+(int(S[0]*1000)%200))]+p
        if kind in ("forged","own_forged"): p=[w.code(R.randrange(len(w.reps)))]+p
        paths[">".join(p)]+=1
    return S,paths

def entries(g,paths):
    now=time.time(); g._rep_idx=None
    return g.spam_entries(now-86400,now-7*86400,{str(int(now//3600*3600)):{"p":dict(paths),"s":{}}},{},{})

res=collections.defaultdict(list)
for ws in (1,2):
    w=World(seed=ws); g=guard_for(w,ws); R=random.Random(50+ws)
    for kind in ("plain","own","forged","own_forged"):
        for t in range(15):
            S,paths=spam(w,R,kind); ent=entries(g,paths)
            for e in ent["entries"]:
                check(e["level"] in ("certain","likely","guess") and isinstance(e["radius_km"],(int,float)) and 5<=e["radius_km"]<=130,"every place says how sure it is and how far the sender can be")
            shown=[e for e in ent["entries"] if e["level"]!="guess"]
            if shown:
                top=max(shown,key=lambda e:e["d7"]); d=km((top["lat"],top["lon"]),S)
                res[kind].append((d,d<=top["radius_km"]))
for kind,v in res.items():
    inside=sum(1 for _,x in v if x)
    check(inside>=0.9*len(v),f"{kind}: the sender is inside the shown area at least 90% of the time ({inside}/{len(v)})")
    check(not any(d>60 for d,_ in v),f"{kind}: nothing shown with confidence more than 60 km from the sender")
check(len(res["plain"])>=20,"ordinary spam is placed with confidence most of the time")

# a first code on its own (nothing after it known) is not certain
w=World(seed=3); g=guard_for(w,3)
learned=g._learned()
ctx=next(((c,n),r) for (c,n),r in learned.items() if n!="ME")
res2=g.resolve_path([ctx[0][0],"7Z"])
check(res2 is None or res2["kind"]!="id" or not res2["sure"],"a first repeater nobody can confirm isn't certain")

# hearing range learnt from adverts, within bounds
rt=getattr(g,"_reach_table",{})
check(rt and all(0<=v for v in rt.values()),"hearing range learnt from adverts")
check(all(5<=g.reach_km(k)<=g.LINK_KM for k in list(rt)[:50]) and g.reach_km("nobody")==g.REACH_DEFAULT_KM,"and kept within sensible bounds")

# copies of a name on the map
w=World(seed=4); g=guard_for(w,4)
HOME=(w.reps[40]["lat"],w.reps[40]["lon"]); AWAY=(w.reps[400]["lat"],w.reps[400]["lon"])   # two made-up spots
real=w.path(w.nearest(HOME)[0]["i"]); cp=w.path(w.nearest(AWAY)[0]["i"])
now=time.time()
dirs={"moorwalker":{"who":"Moor Walker","up":">".join(real),"copies":[[now-600,">".join(cp[:3]),"red",["device","new"],">".join(cp)],[now-300,">".join(cp[:3]),"red",["device","new"],">".join(cp)],[now-200,"X>Y>Z","amber",["new"],">".join(real)]]}}
out=g.copy_places(dirs,{"Moor Walker"},now)
check(len(out)==1 and out[0]["name"]=="Moor Walker" and out[0]["n"]==2 and out[0]["held"],"copies of a name are placed, amber ones left out")
a=out[0]["at"][0] if out else {}
check(a and km((a["lat"],a["lon"]),AWAY)<60,"where the copies came from")
check(out and out[0]["real"] and km((out[0]["real"]["lat"],out[0]["real"]["lon"]),HOME)<60,"and where the real person is heard from")
check(g.copy_places({"x":{"who":"Old","up":"","copies":[[now-600,"A>B>C","red",["device"]]]}},set(),now)==[],"copies saved before 6.45 (no full route) are skipped")

# repeater adverts go into the evidence log with their location, once a day per route
m=mock(); g2=guard(m,floodguard=False,evidence_log=True)
import struct
def advert(name,lat,lon,t=2):
    key=bytes(random.Random(name).getrandbits(8) for _ in range(32))
    app=bytes([t|0x10|0x80])+struct.pack("<ii",int(lat*1e6),int(lon*1e6))+name.encode()
    return (key+struct.pack("<I",int(time.time()))+bytes(64)+app).hex()
evs=[]
g2.ev=lambda r: evs.append(r)
for _ in range(2):
    g2.learn_advert({"payload":advert("Hill Top Rpt",lat=40.12345,lon=-96.23456),"original_path":json.dumps(["AB","CD"]),"timestamp":time.time()})
g2.learn_advert({"payload":advert("Room Srv",39.5,-95.1,t=3),"original_path":json.dumps(["AB"]),"timestamp":time.time()})
g2.learn_advert({"payload":advert("Pocket Phone",39.5,-95.1,t=1),"original_path":json.dumps(["AB"]),"timestamp":time.time()})
rep=[r for r in evs if r.get("node")]
check(len(rep)==2 and rep[0]["node"]=="repeater" and rep[0]["lat"]==40.123 and rep[0]["lon"]==-96.235 and rep[0]["path"]==["AB","CD"],"a repeater advert is logged once with its location, rounded")
check(rep[1]["node"]=="room","room servers too")
check(not any(r.get("lat") is not None and r.get("name")=="Pocket Phone" for r in evs),"a companion's location is never logged")
# a replay rebuilds the advert from that record
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import replay
a=sg.SpamGuard.parse_advert(bytes.fromhex(replay.advert_payload(rep[0])))
check(a and a["type"]==2 and abs(a["lat"]-40.123)<1e-6 and abs(a["lon"]+96.235)<1e-6 and a["name"]=="Hill Top Rpt" and a["key"].startswith(rep[0]["key"]),"a replay rebuilds the advert")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
