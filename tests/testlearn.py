import sys, random, math, collections, logging, time, struct, json
from harness import *
logging.disable(logging.WARNING)
random.seed(7)
km=sg.SpamGuard._km
ME=(51.455,-0.971); SAL=(51.07,-1.79)
def key(code=None):
    c=code or "%02X"%random.randrange(256)
    return c+"".join(random.choice("0123456789ABCDEF") for _ in range(62))
reps=[]
while len(reps)<600:
    lat=random.uniform(50.4,53.6); lon=random.uniform(-4.0,1.6)
    reps.append({"key":key(),"name":f"R{len(reps)}","lat":lat,"lon":lon,"seen":time.time()})
# a listed namesake for the spammer's code far away, and Salisbury-area repeaters
reps.append({"key":key("98"),"name":"Namesake98","lat":51.31,"lon":-0.79,"seen":time.time()})
for i in range(8):
    reps.append({"key":key(),"name":f"Sal{i}","lat":SAL[0]+random.uniform(-.2,.2),"lon":SAL[1]+random.uniform(-.3,.3),"seen":time.time()})
me_rep={"key":"43"+"0"*62,"name":"ME","lat":ME[0],"lon":ME[1]}
nodes=reps+[me_rep]; N=len(nodes); me_i=N-1
adj=[[j for j in range(N) if j!=i and km((nodes[i]["lat"],nodes[i]["lon"]),(nodes[j]["lat"],nodes[j]["lon"]))<45] for i in range(N)]
def route_from(src, jitter=0):
    # randomised shortest-ish path src -> me (excluding both ends)
    dist={me_i:0}; q=collections.deque([me_i])
    while q:
        u=q.popleft()
        for v in adj[u]:
            if v not in dist: dist[v]=dist[u]+1; q.append(v)
    if src not in dist: return None
    p=[]; u=src
    while u!=me_i:
        nxt=[v for v in adj[u] if dist.get(v,1e9)==dist[u]-1]
        u=random.choice(nxt)
        if u!=me_i: p.append(u)
    return p
def advert_payload(n, fake=None):
    lat,lon=fake or (n["lat"],n["lon"])
    return (bytes.fromhex(n["key"])+b"\0"*68+bytes([0x92])+struct.pack("<ii",int(lat*1e6),int(lon*1e6))+n["name"].encode()+b"\0").hex()
m=mock(); g=guard(m)
g.me={"name":"ME","hash":"43","lat":ME[0],"lon":ME[1]}
g.repeaters={"ts":time.time()+1e9,"list":reps}
# a repeater that lies about where it is: actually near Salisbury, claims to be near Gatwick
liar={"key":key("76"),"name":"Liar76","lat":SAL[0]+0.03,"lon":SAL[1]+0.05,"seen":time.time()}
nodes.insert(N-1,liar)  # not used in adj; add adjacency manually below
liar_nbrs=[i for i in range(len(reps)) if km((liar["lat"],liar["lon"]),(reps[i]["lat"],reps[i]["lon"]))<40]
pk=[]; t0=time.time()-3600; hid=0
for i in range(len(reps)):
    for _ in range(3):
        p=route_from(i)
        if p is None: continue
        hid+=1; pk.append({"id":hid,"timestamp":t0+hid*0.01,"type":4,"payload":advert_payload(reps[i]),"packet_hash":f"a{hid}",
                           "original_path":json.dumps([nodes[j]["key"][:2] for j in p])})
for _ in range(40):   # liar's adverts go out through its real neighbours, with a fake location
    s=random.choice(liar_nbrs); p=route_from(s)
    if p is None: continue
    hid+=1; pk.append({"id":hid,"timestamp":t0+hid*0.01,"type":4,"payload":advert_payload(liar,(51.097,-0.103)),"packet_hash":f"a{hid}",
                       "original_path":json.dumps([nodes[j]["key"][:2] for j in [s]+p])})
# the namesake 98 (a real, advertised repeater ~50 km away) adverts through N1, a Salisbury-side neighbour
spam_src=(SAL[0]+0.02,SAL[1]-0.02)
sal_nbrs=[i for i in range(len(reps)) if km(spam_src,(reps[i]["lat"],reps[i]["lon"]))<35]
ns=[r for r in reps if r["name"]=="Namesake98"][0]
N1=min(sal_nbrs,key=lambda i: km((ns["lat"],ns["lon"]),(reps[i]["lat"],reps[i]["lon"])))
ns["lat"],ns["lon"]=reps[N1]["lat"]+0.05,reps[N1]["lon"]+0.68   # ~48 km east of N1
for _ in range(12):
    p=route_from(N1)
    if p is None: continue
    hid+=1; pk.append({"id":hid,"timestamp":t0+hid*0.01,"type":4,"payload":advert_payload(ns),"packet_hash":f"a{hid}",
                       "original_path":json.dumps([nodes[j]["key"][:2] for j in [N1]+p])})
g.ingest(pk)
check("advert routes stored", len(g.adv_routes)>1000, len(g.adv_routes))
t=time.time(); g.learn_step(work_s=999, rest_s=0); L=g._learned()
print("learn time",round(time.time()-t,1),"s, learned",len(L))
check("learned many contexts", len(L)>500, len(L))
# spam: unlisted node coded 98 near Salisbury, sends via Salisbury-area neighbours (mostly N1)
hour=str(int(time.time()//3600*3600)); g.hist={hour:{"m":0,"c":0,"x":0,"g":0,"a":0,"h":{},"p":{}}}
def add(ps,n=1): g.hist[hour]["p"][ps]=g.hist[hour]["p"].get(ps,0)+n
for k in range(80):
    s=N1 if k<45 else random.choice(sal_nbrs); p=route_from(s)
    if p is None: continue
    add(">".join(["98"]+[nodes[j]["key"][:2] for j in [s]+p]))
for _ in range(30):
    s=random.choice(liar_nbrs); p=route_from(s)
    if p is None: continue
    add(">".join([liar["key"][:2]]+[nodes[j]["key"][:2] for j in [s]+p]))
t=time.time(); g.map_refresh(rest_s=0); ent=g._geo["ent"]; print("entries time",round(time.time()-t,2),"s")
st=g.status()["metrics"]; check("status serves the background map result", len(st["entries"])==len(ent["entries"]) and not st["map_working"])
g4=guard(mock()); check("status before the first map result says it's working", g4.status()["metrics"]["map_working"])
for e in ent["entries"][:8]:
    print(" ",e["kind"],e["code"],e["d7"],"sure" if e["exact"]>=e["d7"]/2 else "guess",round(km(SAL,(e["lat"],e["lon"]))),"kmSal",e.get("near"),e.get("claims"),e.get("spread_km"))
e98=[e for e in ent["entries"] if e["code"]=="98" and e["exact"]]
check("98 placed near Salisbury and sure", e98 and km(SAL,(e98[0]["lat"],e98[0]["lon"]))<30, e98[:1])
check("98 not pinned on the far namesake", not any(e["name"]=="Namesake98" and e["exact"] for e in ent["entries"]))
e76=[e for e in ent["entries"] if e["code"]==liar["key"][:2] and e["exact"]]
check("liar's spam placed near Salisbury, not its claimed spot", e76 and km(SAL,(e76[0]["lat"],e76[0]["lon"]))<40, e76[:1])
check("liar named as a claim", any("Liar76" in (e.get("claims") or []) for e in e76))
st=g.metrics() if hasattr(g,"metrics") else None
print(f"{sum(1 for r in RESULTS if r[1])}/{len(RESULTS)} passed")
# backfill on a fresh start reads adverts from openHop
m2=mock(); m2.packets=[dict(p, timestamp=time.time()-3600) for p in pk]; g2=guard(m2)
g2.backfill_adverts()
for _ in range(60):
    if g2._adv_backfill>1: break
    time.sleep(1)
check("backfill reads adverts from openHop", len(g2.adv_routes)==len(g.adv_routes), (len(g2.adv_routes),len(g.adv_routes)))
check("backfill asked only for adverts, in slices", m2.last_q.get("type")=="4" and "end_timestamp" in m2.last_q, m2.last_q)
calls=m2.filtered_calls; g2.backfill_adverts(); time.sleep(1); check("backfill runs once", m2.filtered_calls==calls==14, (calls,m2.filtered_calls))
# location retry: no stats at first -> retried within a minute, not 30
g3=guard(mock()); g3.refresh_openhop_info(force=True)
check("missing location retried soon", time.time()-g3.repeaters["ts"] > 1700, time.time()-g3.repeaters["ts"])
g2._save_state(force=True); st=json.load(open(g2.cfg["state_file"])); check("advert routes not written to the SD card", "adv_routes" not in st)
print(f"{sum(1 for r in RESULTS if r[1])}/{len(RESULTS)} passed")
