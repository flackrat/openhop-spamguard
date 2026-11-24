# FloodGuard's airtime breakdown and congestion holds (experimental). The breakdown counts each kind of packet, the
# repeater it came in through, anonymous requests by sender key, requests to this repeater, and polling that comes
# like clockwork. While the radio is congested, a repeater using far more than its share of airtime on one kind of
# packet is held for that kind only (Watch only: just noted). Channel and direct messages are never held. Made-up data.
import sys, os, json, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
RADIO={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
ME="5A"
def pkt(ts, path, ptype, length=60, payload="", route=1, sent=True):
    return {"id":os.urandom(6).hex(),"timestamp":ts,"type":ptype,"route":route,"length":length,"rssi":-100,"snr":2.0,
            "transmitted":sent,"packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path),"payload":payload}
def setup(**kw):
    g=guard(mock(), floodguard=True, **kw); g.radio=dict(RADIO); g.refresh_openhop_info=lambda *a,**k: None
    g.me={"name":"Test Rptr","hash":ME}; g.fg.update(ready=time.time()-86400, learnt_at=time.time()); return g
now=time.time()
g=setup()
ps=[]
# ordinary traffic: channel messages from several repeaters
for i in range(40): ps.append(pkt(now-1800+i*30, [["1A","2B","3C"][i%3]], 5, length=80))
# a telemetry app polling this repeater every 60 s through 7D (request from code C4 to us)
for i in range(20): ps.append(pkt(now-1500+i*60, ["7D"], 0, length=30, payload=ME+"C4"+"00"*20))
# anonymous requests from one key through 7D
key="AB12CD34"+"00"*28
gaps=[5,80,20,150,40,9,120,30,60,15]
for i in range(10): ps.append(pkt(now-1200+sum(gaps[:i]), ["7D"], 7, length=60, payload=ME+key+"00"*10))
g.ingest(ps)
b=g.fg_breakdown(now)
kinds={k["kind"]:k for k in b["kinds"]}
check(kinds["channel messages"]["packets"]==40 and kinds["requests"]["packets"]==20 and kinds["anonymous requests"]["packets"]==10,"counted by kind: %s"%[(k["kind"],k["packets"]) for k in b["kinds"]])
check(abs(sum(k["share"] for k in b["kinds"])-100)<=2,"shares add up")
check(b["entry"][0]["hop"]=="7D" and b["entry"][0]["main"]=="requests","the busiest way in, and what it mostly carried: %s"%b["entry"][:2])
check(b["to_me"]==30,"requests addressed to this repeater: %s"%b["to_me"])
check(b["anon"] and b["anon"][0]["key"]=="AB12CD34" and b["anon"][0]["to_me"] and b["anon"][0]["packets"]==10,"anonymous requests by key: %s"%b["anon"])
cw=[r for r in b["clockwork"] if r["from"]=="C4"]
check(cw and cw[0]["every"]==60 and cw[0]["to_me"],"polling every 60 s spotted: %s"%b["clockwork"])
check(not any(r["from"]=="AB12CD34" for r in b["clockwork"]),"uneven requests aren't called clockwork")
check(b["holds"]==[],"no holds when off")
# our own transmissions don't count
g.ingest([{"id":"own1","timestamp":now-10,"type":5,"route":1,"length":80,"rssi":0,"snr":0,"packet_hash":"own1","original_path":"[]","payload":""}])
check(g.fg_breakdown(now)["packets"]==70,"this repeater's own packets aren't counted")

# congestion: 7D floods anonymous requests while the radio is very busy
def flood(g, t0, hop="7D", ptype=7, n=300):
    ps=[pkt(t0+i*0.9, [hop,"2B"], ptype, length=120, payload=ME+key+"00"*10) for i in range(n)]
    ps+=[pkt(t0+i*9, [["1A","3C"][i%2]], 5, length=80) for i in range(30)]
    g.ingest(ps)
for mode in ("watch","on"):
    g=setup(source_holds=mode); t0=time.time()-280
    flood(g,t0)
    busy,share,n=g.fg_load(time.time()); check(busy>=15,f"{mode}: the radio is congested ({busy:.0f}%)")
    g.decide()
    held=[k for k,v in g.blocks.items() if v.get("source")=="source-auto"]
    if mode=="watch":
        check(not held,"watch only: nothing held")
        check(any("Watch only" in a["msg"] for a in g.activity),"but it says what it would hold")
        check(g.fg_breakdown()["holds"] and g.fg_breakdown()["holds"][0]["watch"],"shown on the page as would hold")
    else:
        check(held==["ptype:7:7D"],"on: that kind through that repeater is held: %s"%held)
        b=g.blocks.get("ptype:7:7D") or {}
        check(b and b["expires"]-b["created"]<=660,"for ten minutes, then it ends by itself")
        check(not any(v.get("source")=="source-auto" and v["value"].get("ptype")==5 for v in g.blocks.values()),"channel messages never held")
        check(g.fg_breakdown()["holds"][0]["active"],"shown as held now")
# quiet radio: nothing, even with one repeater sending most of a small amount
g=setup(source_holds="on"); t0=time.time()-280
g.ingest([pkt(t0+i*10, ["7D"], 7, length=40, payload=ME+key) for i in range(25)])
g.decide()
check(not any(v.get("source")=="source-auto" for v in g.blocks.values()),"a quiet radio holds nothing")
# a repeater you said never to block is left alone
g=setup(source_holds="on"); g.allow_hops=set(["7D"]) if isinstance(g.allow_hops,set) else ["7D"]
if True:
    flood(g,time.time()-280); g.decide()
    check(not any(v.get("source")=="source-auto" for v in g.blocks.values()),"a never-block repeater isn't held")
# at most three at once
g=setup(source_holds="on"); t0=time.time()-280
for i,h in enumerate(["7D","8E","9F","AA","BB"]):
    flood(g,t0,hop=h,ptype=[0,6,7,0,6][i],n=120)
g.decide()
check(sum(1 for v in g.blocks.values() if v.get("source")=="source-auto")<=3,"at most three congestion holds")
# per radio: only when openHop says which radio heard each packet, and more than one did
g=setup(); t=time.time()
ps=[dict(pkt(t-600+i, ["1A"], 5), rx_radio_id=("radio-a" if i%3 else "radio-b")) for i in range(30)]
g.ingest(ps); r=g.fg_breakdown()["radios"]
check([x["radio"] for x in r]==["radio-a","radio-b"] and sum(x["packets"] for x in r)==30,"airtime by radio: %s"%r)
g=setup(); g.ingest([dict(pkt(t-600+i, ["1A"], 5), rx_radio_id="radio-a") for i in range(10)]+[pkt(t-500, ["1A"], 5)])
check(g.fg_breakdown()["radios"]==[],"one radio, or none reported: nothing shown")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
