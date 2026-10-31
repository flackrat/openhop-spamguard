# What FloodGuard stopped, by the limit that stopped it: the busy hop limit, the unscoped-flood limit, the advert
# limit, and (counted separately) damaged copies not passed on and wardriving packets. The hourly figures add up
# to the old total, and hours counted before the breakdown keep their total.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

m=mock(); g=guard(m); g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
g.refresh_openhop_info=lambda *a,**k: None
g.rule_ids.update({"flood:limit":901,"flood:unscoped":902,"flood:advert":903})
now=time.time()
def pkt(ts,rule,ptype=5,route=1,hops=20):
    return {"id":os.urandom(6).hex(),"timestamp":ts,"type":ptype,"route":route,"length":60,"rssi":-100,"snr":2.0,
            "transmitted":False,"is_duplicate":False,"packet_hash":os.urandom(8).hex(),
            "original_path":json.dumps([os.urandom(1).hex().upper() for _ in range(hops)]),"payload":"00",
            "drop_reason":f"Policy blocked packet (rule {rule})" if rule else ""}
t0=now-1800
for i in range(5): g.fg_observe(pkt(t0+i,901))
for i in range(3): g.fg_observe(pkt(t0+10+i,902))
for i in range(2): g.fg_observe(pkt(t0+20+i,903,ptype=4))
g.fg_observe(pkt(t0+30,0))      # not stopped
hr=str(int(t0//3600*3600))
h=g.hist[hr]
check((h.get("fcl"),h.get("fcu"),h.get("fca"))==(5,3,2), f"split by rule: {h.get('fcl')},{h.get('fcu')},{h.get('fca')}")
check(h.get("fc")==10, f"the total is still kept: {h.get('fc')}")
# an hour counted before the breakdown: only a total
old=str(int((now-5*3600)//3600*3600))
g.hist[old]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"fc":7}
met=g.status()["metrics"]
rows={r["t"]:r for r in met["hourly"]}
r=rows[int(hr)]
check((r["fcl"],r["fcu"],r["fca"],r["fc"])==(5,3,2,10), f"the hourly figures carry it: {r['fcl']},{r['fcu']},{r['fca']},{r['fc']}")
ro=rows[int(old)]
check(ro["fc"]==7 and ro["fcl"]==0, "an older hour keeps only its total")
check(met["d1"]["fcl"]==5 and met["d1"]["fcu"]==3 and met["d1"]["fca"]==2 and met["d1"]["fc"]==17, f"24 h totals: {met['d1']['fcl']},{met['d1']['fcu']},{met['d1']['fca']},{met['d1']['fc']}")
check(all(k in r for k in ("ds","ws")), "damaged and wardriving counts are in each hour")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
