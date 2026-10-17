# FloodGuard: contains floods of any packet type by how busy the radio is, not by who sent them.
# Checks the rules against openHop's own rule engine: flood packets from far away are held back while
# the radio is flooded, direct packets and known people's channel messages never are, the limit tightens
# while the flood lasts and lifts by itself, and the fixed hop limits for unscoped packets and adverts.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

RADIO={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
def pkt(ts, hops, route=1, ptype=2, length=60, sent=True, drop=None):
    p={"id":os.urandom(6).hex(),"timestamp":ts,"type":ptype,"route":route,"length":length,"rssi":-100,"snr":2.0,
       "transmitted":sent,"is_duplicate":False,"packet_hash":os.urandom(8).hex(),
       "original_path":json.dumps([os.urandom(1).hex().upper() for _ in range(hops)]),"payload":""}
    if drop: p["drop_reason"]=drop; p["transmitted"]=False
    return p
class P:
    def __init__(s, sender=None, text=None, hops=0):
        s.path=[os.urandom(1).hex().upper() for _ in range(hops)]
        s.payload=bytearray(bytes.fromhex(enc(sender,text))) if sender else bytearray(os.urandom(40)); s.transport_codes=[0,0]
    def get_path_hashes_hex(s): return s.path
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def verdict(m, route, hops, ptype=2, sender=None, text=None):
    pe=m.policy["policy_engine"]
    return PolicyEngine(pe).evaluate(P(sender,text,hops),{"route_type":route,"payload_type":ptype,"hop_count":hops,
                                                          "local_transmission":False}).action

m=mock(); g=guard(m, known_min_msgs=3); g.radio=dict(RADIO)
g.refresh_openhop_info=lambda *a,**k: None   # the fake openHop has no radio settings to read
# ---- ordinary day: flood packets come from 1-7 hops, radio a few % busy
now=time.time()
day=[pkt(now-20*3600+i*220, random.choice([1,2,2,3,3,3,4,4,5,6,7])) for i in range(300)]
g.ingest(day); g.fg_decide()
check(g.airtime_ms(60)>300, f"airtime known ({g.airtime_ms(60):.0f} ms for 60 bytes)")
g.apply_settings({"mode":"protect"})
# a regular, so known-people rules have someone in them
for i,t in enumerate(["Morning all from the hill","Nice and clear today","Anyone near the canal?"]):
    m.add("Quarry Pete",t,["4C","2F"],ago=600-i*60)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Quarry Pete"),"regular is known")
check(not g._build_flood(),"FloodGuard off by default: no rules")

check(g.fg_reach() in (5,6,7), f"learns how far flood packets normally come: {g.fg_reach()}")
check(not g.fg.get("limit"),"no limit on an ordinary day")

# ---- turn FloodGuard on, then a flood: 25 packets a minute from 20-40 hops away for 6 minutes
g.apply_settings({"floodguard":True,"flood_hop_floor":4})
t0=time.time()
flood=[pkt(t0-360+i*2.4, random.randint(20,40)) for i in range(150)]
g.ingest(flood)
check(not g.fg_decide(t0) and not g.fg.get("limit"),"waits a minute before stepping in")
busy,share,n=g.fg_load(t0)
check(busy>=15 and share>0.9, f"measures the radio as busy ({busy:.0f}%, {share:.0%} flood)")
changed=g.fg_decide(t0+61)
lim=g.fg.get("limit")
check(changed and lim and 8<=lim<=8+8, f"steps in after a minute, just above normal reach (limit {lim})")
check(g.fg_reach() in (5,6,7), f"the flood's padded routes don't count as normal: {g.fg_reach()}")
g.last_sync=0; g.sync_pending=True; g.poll_once()
check(verdict(m,1,30)=="drop","a flood packet from 30 hops away is not passed on")
check(verdict(m,0,30)=="drop","nor a scoped (transport) flood packet from 30 hops")
check(verdict(m,1,3)=="allow","a flood packet from 3 hops away still is")
check(verdict(m,2,30)=="allow","direct (routed) packets are never touched")
check(verdict(m,3,30)=="allow","nor transport-direct packets")
check(verdict(m,1,30,5,"Quarry Pete","Hello from far away tonight")=="allow","a known person's channel message from far away gets through")
check(verdict(m,1,30,5,rname(),"Hello from far away tonight")=="drop","an unknown name's from that far doesn't, while the flood lasts")
names=[r["name"] for r in m.policy["policy_engine"]["rules"]]
fi=[i for i,n in enumerate(names) if "flood-limit" in n]; ki=[i for i,n in enumerate(names) if "known-people" in n]
check(fi and ki and ki[0]<fi[0], "known-people rule comes before the flood limit")
check(names.index("my own rule")<fi[0],"after your own rules")

# ---- counting: packets openHop says the FloodGuard rule stopped
rid=g.rule_ids["flood:limit"]
t1=time.time()
g.ingest([pkt(t1+i*0.05, 30, drop=f"Policy blocked packet (rule {rid})") for i in range(20)])
mt=g.metrics(); h=mt["hourly"][-1]
check(h["fc"]>=20, f"stopped flood packets counted per hour ({h['fc']})")
check(mt["d1"]["fc"]>=20 and mt["d1"]["fs"]>0, "and in the 24 h totals with airtime saved")
check(h.get("bz") and h["bz"]>=15, f"busiest five minutes recorded ({h.get('bz')}%)")
st=mt["floodguard"]
check(st["enabled"] and st["limit"]==g.fg["limit"] and rid in st["rules"], "status says what's in force")

# ---- the flood goes on and gets heavier: tightens two hops at a time, never below the floor
more=[pkt(t1+2+i*2.4, random.randint(20,40)) for i in range(800)]
g.ingest(more)
seen=[g.fg["limit"]]
for k in range(1,14):
    g.fg_decide(t0+61+k*121); seen.append(g.fg["limit"])
check(seen[-1]>=4 and all(b<=a for a,b in zip(seen,seen[1:])) and all(a-b<=2 for a,b in zip(seen,seen[1:])),
      f"tightens two hops at a time, never below the floor of 4: {seen}")
check(seen[-1]<seen[0],"does tighten while the radio stays busy")

# ---- the flood stops: lifted after the radio has been quiet for 10 minutes
tq=t1+2+800*2.4
g.fg_decide(tq+400)      # window empty now
check(g.fg.get("limit"),"not lifted the moment it goes quiet")
g.fg_decide(tq+400+601)
check(not g.fg.get("limit"),"lifted after ten quiet minutes")
check(any("lifted" in a["msg"] for a in g.activity),"says so in Activity")
g.last_sync=0; g.sync_pending=True; g.poll_once()
check(verdict(m,1,30)=="allow","far flood packets get through again")
check(not any("flood-limit" in r["name"] for r in m.policy["policy_engine"]["rules"]),"rule removed from openHop")

# ---- Monitor: rule only logs
g.fg.update(limit=12, since=time.time(), last_step=time.time())
g.apply_settings({"mode":"monitor"})
g.last_sync=0; g.sync_pending=True; g.poll_once()
r=[r for r in m.policy["policy_engine"]["rules"] if "flood-limit" in r["name"]]
check(r and r[0]["then"]["action"]=="log_only","in Monitor the flood rule only logs")
g.ingest([pkt(time.time()-5+i*0.1, 30) for i in range(5)])
check(g.metrics()["hourly"][-1]["fx"]>=5,"and over-limit packets passed on are counted as let through")
g.apply_settings({"mode":"protect"}); g.fg.update(limit=None)

# ---- fixed hop limits (MeshCore's flood.max.unscoped and flood.max.advert)
check(g.cfg["flood_max_unscoped"]==32 and g.cfg["flood_max_advert"]==8,"recommended hop limits come set: 32 unscoped, 8 adverts")
g.apply_settings({"floodguard":False})
g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not any("floodguard" in r["name"] for r in m.policy["policy_engine"]["rules"]),"FloodGuard off: no hop limits either")
check(verdict(m,1,40)=="allow" and verdict(m,1,9,4)=="allow","nothing dropped by hops with FloodGuard off")
g.apply_settings({"floodguard":True,"flood_max_unscoped":16})
g.fg.update(limit=None)
g.last_sync=0; g.sync_pending=True; g.poll_once()
check(verdict(m,1,16)=="drop","unscoped flood packet that has had 16 hops is dropped")
check(verdict(m,1,15)=="allow","15 hops is fine")
check(verdict(m,0,20)=="allow","a scoped flood packet isn't affected by the unscoped limit")
check(verdict(m,1,9,4)=="drop" and verdict(m,0,9,4)=="drop","an advert from 9 hops is dropped, scoped or not")
check(verdict(m,1,7,4)=="allow","an advert from 7 hops gets through")
check(verdict(m,2,40,4)=="allow","a direct packet is never touched")
check(verdict(m,1,20,5,"Quarry Pete","Evening from the far valley")=="allow","known people's channel messages still pass the unscoped limit")

# a value you saved yourself is kept, also 0 (off), and survives a restart
g.apply_settings({"flood_max_advert":0}); g._save_state(force=True)
gk=sg.SpamGuard(dict(g.file_cfg)); gk.refresh_openhop_info=lambda *a,**k: None
check(gk.cfg["flood_max_advert"]==0 and gk.cfg["flood_max_unscoped"]==16,"your own values (including 0) are kept, not reset to the recommended ones")
g.apply_settings({"flood_max_advert":8})
# ---- saved across a restart
g._save_state(force=True)
g2=sg.SpamGuard(dict(g.file_cfg)); g2.radio=dict(RADIO); g2.refresh_openhop_info=lambda *a,**k: None
check(g2.fg_hops and g2.fg_reach()==g.fg_reach(),"what it learnt about normal routes survives a restart")
check(g2.fg["mark"]==g.fg["mark"],"and which packets it has already counted")
before=g2.metrics()["d1"]["fc"]; g2.ingest(flood); after=g2.metrics()["d1"]["fc"]
check(before==after,"packets read again after a restart aren't counted twice")

# ---- radio settings unknown: does nothing
g3=guard(mock(), floodguard=True); g3.ingest(flood)
check(not g3.fg_decide(time.time()) and not g3.fg.get("limit"),"no radio settings: FloodGuard waits")

print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
