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
check(g.cfg["floodguard"],"FloodGuard is on by default")
g.fg_decide(time.time())
st=g.fg_status()
check(st["learning"] and st["learn_until"]-time.time()>2.9*86400, "and starts by learning for three days")
check(any("learns how busy" in a["msg"] for a in g.activity),"says so in Activity")
r=g._build_flood()
check(r and all(x["then"]["action"]=="log_only" for x in r),"while learning its rules only count, even in Protect")
g.fg.update(ready=time.time(), learnt_at=time.time())   # the rest of this test: learning already done

check(g.fg_reach() in (5,6,7), f"learns how far flood packets normally come: {g.fg_reach()}")
check(not g.fg.get("limit"),"no limit on an ordinary day")

# ---- turn FloodGuard on, then a flood: 25 packets a minute from 20-40 hops away for 6 minutes
g.apply_settings({"flood_hop_floor":4})
t0=time.time()
flood=[pkt(t0-360+i*2.4, random.randint(20,40)) for i in range(150)]
g.ingest(flood)
check(g.fg_decide(t0) and not g.fg.get("limit"),"learning is done, so the rules change from counting to holding back (and it doesn't step in yet)")
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

# ---- learning: three days of this repeater's own traffic set the automatic values
g5=guard(mock()); g5.radio=dict(RADIO); g5.refresh_openhop_info=lambda *a,**k: None
T=time.time(); g5.fg["learn_start"]=T-2*86400
check(not g5.fg_learn(T) and not g5.fg.get("ready"),"not before three days")
g5.fg["learn_start"]=T-3.1*86400
for k in range(80):
    hr=str(int((T-k*3600)//3600*3600))
    g5.hist[hr]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":round(random.uniform(2,5),1)}
    g5.fg_hops[hr]={h:random.randint(1,4) for h in range(1,8)}
    g5.fg_adv[hr]={h:1 for h in range(1,7)}
    g5.fg_hops_all[hr]=dict(g5.fg_hops[hr]); g5.fg_adv_all[hr]=dict(g5.fg_adv[hr])
check(g5.fg_learn(T) and g5.fg.get("ready"),"after three days with enough traffic it starts acting")
L=dict(g5.fg["learnt"])
check(10<=L.get("flood_busy_percent",0)<=15 and L.get("flood_max_unscoped")==16 and L.get("flood_max_advert")==8, f"learnt values from this mesh, inside their safe ranges: {L}")
check(g5.cfg["flood_max_unscoped"]==16 and g5.cfg["flood_busy_percent"]==L["flood_busy_percent"],"and they're in force")
check(any("has learnt this repeater's traffic" in a["msg"] for a in g5.activity),"says so in Activity")
g5.apply_settings({"flood_max_unscoped":24})
for k in range(80):   # the mesh gets busier and routes longer
    hr=str(int((T-k*3600)//3600*3600)); g5.hist[hr]["bz"]=9.0; g5.fg_hops[hr]={h:3 for h in range(1,15)}
check(not g5.fg_learn(T+3600),"checks again only once a day")
g5.fg_learn(T+86400+60); L2=g5.fg["learnt"]
check(L2["flood_busy_percent"]==L["flood_busy_percent"]+5,f"adjusts a little at a time: {L['flood_busy_percent']} -> {L2['flood_busy_percent']}")
check(g5.cfg["flood_max_unscoped"]==24,"a value you set yourself is never changed")
g5.action("fg_auto",{"key":"flood_max_unscoped"})
check(g5.cfg["flood_max_unscoped"]==L2["flood_max_unscoped"],"Back to automatic puts the learnt value back")
g5._save_state(force=True); g6=sg.SpamGuard(dict(g5.file_cfg))
check(g6.fg.get("ready") and g6.cfg["flood_max_unscoped"]==L2["flood_max_unscoped"],"what it learnt survives a restart")
# Reset and learn again: everything back to FloodGuard's own values, learnt afresh, still protecting meanwhile
g5.apply_settings({"flood_max_advert":12,"flood_hop_floor":6})
g5.action("fg_relearn",{})
check(not any(k in g5.settings for k in ("flood_max_advert","flood_hop_floor","flood_max_unscoped")),"reset clears values you set")
check(g5.cfg["flood_max_unscoped"]==32 and g5.cfg["flood_max_advert"]==8 and g5.cfg["flood_hop_floor"]==8,"back to the recommended values while it learns")
st=g5.fg_status(); check(st["learning"] and st["relearning"],"status says it is learning again")
g5.apply_settings({"mode":"protect"})
check(all(r["then"]["action"]=="drop" for r in g5._build_flood()),"and it keeps protecting while it re-learns")
T2=T+86400+120
check(not g5.fg_learn(T2+86400),"waits three days again")
for k in range(80):   # new traffic after the reset: a long-haul mesh now
    hr=str(int((T2+3*86400-k*3600)//3600*3600))
    g5.hist[hr]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":3.0}
    g5.fg_hops[hr]={h:2 for h in range(1,14)}; g5.fg_adv[hr]={h:1 for h in range(1,7)}
CLK=T2+3.1*86400
real=time.time; time.time=lambda: CLK
try:
    check(g5.fg_learn(CLK) and not g5.fg.get("relearn"),"after three days it switches to what it learnt again")
finally:
    time.time=real
check(g5.cfg["flood_max_unscoped"]>=24,f"learnt from the new traffic only: unscoped {g5.cfg['flood_max_unscoped']}")
g7=guard(mock()); g7.radio=dict(RADIO); g7.refresh_openhop_info=lambda *a,**k: None; g7.fg_decide(time.time())
g7.action("fg_start_now",{})
check(g7.fg.get("ready") and g7.cfg["flood_max_unscoped"]==32,"Start protecting now: acts straight away with the recommended values")
g7.apply_settings({"floodguard":False}); g7.last_sync=0
check(not g7._build_flood(),"turned off: no FloodGuard rules")

# ---- upgrading from 6.0: FloodGuard values set by hand there are cleared once, the on/off choice is kept
st6=os.path.join(TMP,"state_v60.json"); m8=mock(); U=f"http://127.0.0.1:{m8.srv.server_address[1]}"
json.dump({"settings":{"floodguard":True,"flood_busy_percent":25,"flood_max_unscoped":20,"flood_hop_floor":6,"mode":"protect"},
           "floodguard":{"episodes":1}},open(st6,"w"))
g8=sg.SpamGuard({"openhop_url":U,"state_file":st6})
check(not any(k in g8.settings for k in ("flood_busy_percent","flood_max_unscoped","flood_hop_floor")),"6.0 FloodGuard values cleared on upgrade")
check(g8.settings.get("floodguard") is True and g8.settings.get("mode")=="protect","FloodGuard on/off and other settings kept")
check(any("values set in 6.0 were cleared" in a["msg"] for a in g8.activity),"says so in Activity")
g8.apply_settings({"flood_max_unscoped":24}); g8._save_state(force=True)
g9=sg.SpamGuard({"openhop_url":U,"state_file":st6})
check(g9.settings.get("flood_max_unscoped")==24,"only once: values set after upgrading are kept")
gf=sg.SpamGuard({"openhop_url":U,"state_file":os.path.join(TMP,"fresh61.json")})
gf.apply_settings({"flood_max_advert":10}); gf._save_state(force=True)
gf2=sg.SpamGuard({"openhop_url":U,"state_file":os.path.join(TMP,"fresh61.json")})
check(gf2.settings.get("flood_max_advert")==10,"a fresh 6.1 install keeps its values across restarts")

# ---- resets: settings back to defaults (FloodGuard's too); Start again from scratch makes FloodGuard learn again
gr=guard(mock()); gr.radio=dict(RADIO); gr.refresh_openhop_info=lambda *a,**k: None
gr.fg.update(ready=time.time(), learnt={"flood_max_unscoped":20}, learn_start=time.time()-5*86400, episodes=3); gr.rebuild_cfg()
gr.apply_settings({"flood_busy_percent":25,"flood_hop_floor":6})
gr.apply_settings({"reset":True})
check(gr.cfg["flood_busy_percent"]==15 and gr.cfg["flood_hop_floor"]==8,"Reset puts FloodGuard settings you changed back too")
check(gr.cfg["flood_max_unscoped"]==20,"and keeps what it learnt")
gr.reset_all()
check(not gr.fg.get("ready") and not gr.fg.get("learnt") and gr.cfg["flood_max_unscoped"]==32 and not gr.fg.get("episodes"),
      "Start again from scratch: FloodGuard forgets what it learnt")
gr.fg_decide(time.time())
check(gr.fg_status()["learning"] and not gr.fg_status()["acting"],"and learns again, only counting")
# a flood while learning is only counted, and says so
gq=guard(mock(), mode="protect"); gq.radio=dict(RADIO); gq.refresh_openhop_info=lambda *a,**k: None
t=time.time(); gq.fg_decide(t)
gq.ingest([pkt(t+i*2.4, random.randint(20,40)) for i in range(150)])
gq.fg_decide(t+360); gq.fg_decide(t+430)
check(gq.fg.get("limit") and not gq.fg_status()["acting"],"learning: a flood is seen but FloodGuard isn't acting")
check(any("only counts them" in a["msg"] for a in gq.activity),"and Activity says it's only counting")
check(all(r["then"]["action"]=="log_only" for r in gq._build_flood()),"and its rules only log")

# ---- radio settings unknown: does nothing
g3=guard(mock(), floodguard=True); g3.ingest(flood)
check(not g3.fg_decide(time.time()) and not g3.fg.get("limit"),"no radio settings: FloodGuard waits")

# ---- a repeater in a busy place: the radio sits above the starting limit, so no hour is "quiet" and the
# old learning (quiet hours only) could never raise the limit. It now takes every hour and uses the middle one.
gb=guard(mock()); gb.radio=dict(RADIO); gb.refresh_openhop_info=lambda *a,**k: None
T=time.time(); gb.fg["learn_start"]=T-3.1*86400
for k in range(80):
    hr=str(int((T-k*3600)//3600*3600))
    gb.hist[hr]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":round(random.uniform(22,30),1)}
for k in (3,4,5):   # and a flood of a few hours inside it doesn't move the middle
    gb.hist[str(int((T-k*3600)//3600*3600))]["bz"]=70.0
check(gb.fg_learn(T) and gb.fg.get("ready"),"a busy repeater finishes learning")
check(gb.fg["learnt"].get("flood_busy_percent")==sg.SpamGuard.BUSY_SITE_CEILING and gb.cfg["flood_busy_percent"]==30,f"and learns a higher busy limit, stopping at the busy-site ceiling: {gb.fg['learnt']}")
check(any("busy most of the time" in a["msg"] for a in gb.activity),"and says why in Activity")
# a quiet repeater still learns exactly as before, and the busy-site fallback is not used for it
check(not g5.fg.get("busy_site") and 10<=g5.fg["learnt"]["flood_busy_percent"]<=20,"a quiet repeater's limit is learnt from its quiet hours, as before")
# too little history: nothing learnt, nothing invented
gn=guard(mock()); gn.radio=dict(RADIO); gn.refresh_openhop_info=lambda *a,**k: None
gn.fg["learn_start"]=T-3.1*86400
for k in range(20): gn.hist[str(int((T-k*3600)//3600*3600))]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":30.0}
check("flood_busy_percent" not in gn.fg_learnt_values(T),"under two days of hours: no busy limit is learnt")
gb._save_state(force=True); gb2=sg.SpamGuard(dict(gb.file_cfg))
check(gb2.fg.get("busy_site") and gb2.cfg["flood_busy_percent"]==30,"the busy-site limit survives a restart")

# ---- a busy mesh where long routes are normal (the evidence log from a real repeater: middle message 10 hops,
# one in four 16 or more, one in ten 20 or more) and the radio is never "quiet". Before 6.5.5 FloodGuard never
# learnt this, started at a made-up 16 hops and tightened to 8, holding back genuine messages.
def busy_guard():
    gb=guard(mock()); gb.radio=dict(RADIO); gb.refresh_openhop_info=lambda *a,**k: None
    T=time.time(); gb.fg.update(ready=T-3600, learn_start=T-4*86400, learnt_at=T)
    for k in range(30):
        hr=str(int((T-k*3600)//3600*3600))
        gb.hist[hr]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":round(random.uniform(18,32),1)}
        gb.fg_hops_all[hr]={h:n for h,n in zip((4,6,8,10,12,16,20,24,29),(4,6,8,9,9,7,5,3,1))}
        gb.fg_adv_all[hr]={h:n for h,n in zip((4,8,12,16),(4,3,2,1))}
    return gb,T
gb,T=busy_guard()
rb=gb.fg_reach()
check(rb is not None and 18<=rb<=24 and gb.fg.get("reach_all"), f"on a busy mesh route length is learnt from every hour: {rb}")
check(gb.fg_can_act() and gb.fg_status()["acting"] and gb.fg_status()["reach_all"] and not gb.fg_status()["waiting_reach"],"and FloodGuard may act")
gb.fg["busy_now"]=27; flood=[pkt(T-360+i*2.4, random.randint(20,40)) for i in range(150)]
gb.ingest(flood); gb.fg_decide(T); gb.fg_decide(T+61)
check(gb.fg.get("limit") and gb.fg["limit"]>=rb-4, f"its limit starts above the ordinary routes, not at 8: {gb.fg.get('limit')} (ordinary routes reach {rb})")
check(gb._build_flood() and any(r["then"]["action"]=="drop" for r in gb._build_flood()),"and its rules hold packets back")
# every flood packet is counted for this, flood or not
gc=guard(mock()); gc.radio=dict(RADIO); gc.refresh_openhop_info=lambda *a,**k: None
gc.ingest([pkt(time.time()-700+i, 12) for i in range(60)]); gc.fg_decide(time.time())
check(sum(sum(v.values()) for v in gc.fg_hops_all.values())>=50,"hop counts are kept for every hour, not only quiet ones")
# learnt values for the fixed limits come from every hour too
Lb=gb.fg_learnt_values(T)
check(Lb.get("flood_max_unscoped")==32 and 6<=Lb.get("flood_max_advert",0)<=16, f"the always-on limits are learnt from this mesh, not the made-up defaults: {Lb}")
# too little heard: it only counts, and says why
gw=guard(mock()); gw.radio=dict(RADIO); gw.refresh_openhop_info=lambda *a,**k: None
gw.fg.update(ready=time.time()-60, learnt_at=time.time()); gw.cfg["mode"]="protect"
check(gw.fg_reach() is None and not gw.fg_can_act(),"too few flood packets heard: route length unknown, so no holding back")
stw=gw.fg_status(); check(stw["waiting_reach"] and not stw["acting"],"the page is told why")
check(all(r["then"]["action"]=="log_only" for r in gw._build_flood()),"and the rules only log")
gw.apply_settings({"flood_hop_floor":10})
check(gw.fg_can_act() and gw.fg_status()["acting"] and not gw.fg_status()["waiting_reach"],"setting your own lowest hop limit lets it act")
check(all(r["then"]["action"]=="drop" for r in gw._build_flood()),"and then the rules hold packets back")
# the note when learning ends says where each limit comes from
gl=guard(mock()); gl.radio=dict(RADIO); gl.refresh_openhop_info=lambda *a,**k: None
gl.fg["learn_start"]=time.time()-4*86400; gl.settings["flood_max_advert"]=6; gl.rebuild_cfg(); gl.fg["start_now"]=True
gl.fg_learn(time.time())
note=[a["msg"] for a in gl.activity if "has learnt this repeater's traffic and now acts" in a["msg"]]
check(note and "adverts stop after 6 hops (yours)" in note[0] and "(recommended)" in note[0] and note[0].count("(yours)")==1, f"values are labelled yours or recommended, not all 'yours': {note[:1]}")
# saved across a restart
gb._save_state(force=True); gb2=sg.SpamGuard(dict(gb.file_cfg))
check(sum(sum(v.values()) for v in gb2.fg_hops_all.values())==sum(sum(v.values()) for v in gb.fg_hops_all.values()) and gb2.fg_adv_all,"the every-hour counts survive a restart")


# ---- a flood must not become "normal": hours FloodGuard flagged as floods are left out of busy-site learning,
# and if flood hours are most of what it heard, it learns nothing from them.
def busy_guard(bz_for, flagged):
    x=guard(mock()); x.radio=dict(RADIO); x.refresh_openhop_info=lambda *a,**k: None
    x.fg["learn_start"]=T-3.1*86400
    for k in range(80):
        x.hist[str(int((T-k*3600)//3600*3600))]={"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{},"bz":bz_for(k),**({"fc":1} if flagged(k) else {})}
    return x
gf1=busy_guard(lambda k: 24.0 if k%4 else 38.0, lambda k: k%4==0)      # a quarter of the hours were flagged floods
v=gf1.fg_learnt_values(T).get("flood_busy_percent")
check(v==30 and gf1.fg.get("busy_site"),f"flagged flood hours are left out of the busy-site middle: {v}")
gf2=busy_guard(lambda k: 24.0 if k%4==0 else 38.0, lambda k: k%4!=0)   # three quarters flagged: a flood dominated
check("flood_busy_percent" not in gf2.fg_learnt_values(T) and not gf2.fg.get("busy_site"),"flood hours are most of what it heard: no busy limit is learnt")
gf3=busy_guard(lambda k: 12.0, lambda k: False)                        # a mildly busy radio: below the ceiling, so unchanged
check(gf3.fg_learnt_values(T).get("flood_busy_percent")==24,"a busy limit below the ceiling is left exactly as learnt")

# ---- 6.15: routed packets can't dilute the flood share; bursts that keep coming back are acted on sooner
def air_guard():
    x=guard(mock()); x.radio=dict(RADIO); x.refresh_openhop_info=lambda *a,**k: None
    return x
xa=air_guard(); ms=xa.airtime_ms(60); t0=time.time()
for i in range(40): xa.air.append((t0-200+i*4, ms*2, True, False, False))
for i in range(60): xa.air.append((t0-200+i*3, ms*2, False, True, False))      # routed packets filling the air
busy,share,n=xa.fg_load(t0)
check(share>0.95 and busy>0, f"routed packets add to busy but not to the flood share ({share:.2f})")
def flooded_guard():
    x=air_guard(); x.cfg["mode"]="protect"; x.fg.update(ready=1, learn_start=T-5*86400, learnt_at=T); x.fg_can_act=lambda: True
    return x
def load(x, now, on):
    x.air.clear()
    if on:
        for i in range(60): x.air.append((now-250+i*4, x.airtime_ms(60)*40, True, False, False))
xb=flooded_guard(); t=T+10
for k in range(2):   # two short bursts, each over before FloodGuard steps in
    load(xb,t,True); xb.fg_decide(t); t+=10; load(xb,t,False); xb.fg_decide(t); t+=30
check(len(xb._pulses)==2 and not xb.fg.get("limit"), "short bursts are remembered but do not start a limit")
load(xb,t,True); xb.fg_decide(t); t+=25; load(xb,t,True); xb.fg_decide(t)
check(xb.fg.get("limit"), "a third burst that lasts only 25 seconds now starts the limit")
xc=flooded_guard(); t=T+10
load(xc,t,True); xc.fg_decide(t); t+=25; load(xc,t,True); xc.fg_decide(t)
check(not xc.fg.get("limit"), "with no earlier bursts, 25 seconds is still too short")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
