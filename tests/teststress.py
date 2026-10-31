import sys, random, math, collections, logging, time, struct, json, threading
from harness import *
logging.disable(logging.WARNING)
random.seed(11)
km=sg.SpamGuard._km
ME=(51.455,-0.971)
def key(): return "".join(random.choice("0123456789ABCDEF") for _ in range(64))
reps=[{"key":key(),"name":f"R{i}","lat":random.uniform(50.2,55.5),"lon":random.uniform(-5.5,1.8),"seen":time.time()} for i in range(5300)]
cell=collections.defaultdict(list)
for i,r in enumerate(reps): cell[(int(r["lat"]*3),int(r["lon"]*2))].append(i)
def nbrs(i):
    r=reps[i]; cx,cy=int(r["lat"]*3),int(r["lon"]*2)
    return [j for dx in (-1,0,1) for dy in (-1,0,1) for j in cell[(cx+dx,cy+dy)] if j!=i and km((r["lat"],r["lon"]),(reps[j]["lat"],reps[j]["lon"]))<35]
def walk(i):
    p=[]; cur=i
    for _ in range(25):
        d=km((reps[cur]["lat"],reps[cur]["lon"]),ME)
        if d<30: return p
        ns=[j for j in nbrs(cur) if km((reps[j]["lat"],reps[j]["lon"]),ME)<d-5]
        if not ns: return None
        cur=random.choice(ns); p.append(cur)
    return None
def adv(n):
    return (bytes.fromhex(n["key"])+b"\0"*68+bytes([0x92])+struct.pack("<ii",int(n["lat"]*1e6),int(n["lon"]*1e6))+n["name"].encode()+b"\0").hex()
pk=[]; hid=0; tries=0
while len(pk)<8000 and tries<40000:
    tries+=1; i=random.randrange(len(reps))
    if km((reps[i]["lat"],reps[i]["lon"]),ME)>350: continue
    p=walk(i)
    if not p: continue
    hid+=1; pk.append({"id":hid,"timestamp":time.time()-3600+hid*0.01,"type":4,"payload":adv(reps[i]),"packet_hash":f"a{hid}","original_path":json.dumps([reps[j]["key"][:2] for j in p])})
print("adverts",len(pk))
m=mock(); g=guard(m, map_directory=True)
g.me={"name":"ME","hash":"43","lat":ME[0],"lon":ME[1]}
g.repeaters={"ts":time.time()+1e9,"list":reps[:850]}
g.public_reps={"ts":time.time()+1e9,"list":reps[850:],"error":None}
g.ingest(pk); print("routes",len(g.adv_routes))
hour=str(int(time.time()//3600*3600)); g.hist={hour:{"m":0,"c":0,"x":0,"g":0,"a":0,"h":{},"p":{}}}
for _ in range(350):
    i=random.randrange(len(reps)); p=walk(i)
    if p: g.hist[hour]["p"][">".join(["6F"]+[reps[j]["key"][:2] for j in p])]=1
stop=threading.Event()
t0=time.time(); th=threading.Thread(target=g.map_loop,args=(stop,),daemon=True); th.start()
worst=0; n=0
while th.is_alive() and (g.__dict__.get("_geo") or {}).get("ent") is None or not g._learned():
    t=time.time(); g.status(); dt=time.time()-t; worst=max(worst,dt); n+=1
    with g.lock: pass
    time.sleep(0.5)
    if time.time()-t0>900: break
print(f"background learning+map took {time.time()-t0:.0f}s here; {n} status calls while it ran, slowest {worst*1000:.0f} ms")
check("status stays fast while the map is worked out", worst<1.0, worst)
check("map result appears", g._geo["ent"] is not None and len(g._learned())>1000, len(g._learned()))
stop.set()
print(f"{sum(1 for r in RESULTS if r[1])}/{len(RESULTS)} passed")
