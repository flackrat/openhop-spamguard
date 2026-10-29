# Damaged copies: channel packets whose 2-byte check value fails, for a channel SpamGuard holds the key for.
# They are counted and shown, they take airtime (so they count towards "busy"), but up to a quarter of the
# airtime they are left out of the flood share, and any more than that counts as flood traffic so junk with a
# bad check can't be used to hide a real flood.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

RADIO={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
def gpkt(ts, payload_hex, hops=3, length=60):
    return {"id":os.urandom(6).hex(),"timestamp":ts,"type":5,"route":1,"length":length,"rssi":-100,"snr":2.0,
            "transmitted":True,"is_duplicate":False,"packet_hash":os.urandom(8).hex(),
            "original_path":json.dumps([os.urandom(1).hex().upper() for _ in range(hops)]),"payload":payload_hex}
def damage(h):
    b=bytearray(bytes.fromhex(h)); b[-1]^=0x70; return b.hex()    # one nibble of the last byte changes
chans={"Public":sg.PUBLIC_CHANNEL_KEY}
good=enc("Quarry Pete","hello there")
check(sg.group_text_state(bytes.fromhex(good),chans)=="ok","a good packet is ok")
check(sg.group_text_state(bytes.fromhex(damage(good)),chans)=="bad","a damaged copy is bad")
other=bytes([(bytes.fromhex(good)[0]+1)%256])+bytes.fromhex(good)[1:]
check(sg.group_text_state(other,chans)=="other","a channel we hold no key for can't be judged")
check(sg.group_text_state(b"\x11\x00",chans)=="other","too short can't be judged")

m=mock(); g=guard(m); g.radio=dict(RADIO)
g.refresh_openhop_info=lambda *a,**k: None
now=time.time()
# 100 good Public packets and 30 damaged copies spread over the last 20 hours
pk=[]
for i in range(100): pk.append(gpkt(now-20*3600+i*600, enc("Pete%d"%i,"msg %d"%i)))
for i in range(30): pk.append(gpkt(now-20*3600+i*1900+5, damage(enc("Pete%d"%i,"msg %d"%i))))
pk.sort(key=lambda p:p["timestamp"])
g.ingest(pk); g.fg_decide()
d=g.damaged_stats()
check(d["packets"]==130 and d["damaged"]==30, f"counted: {d}")
check(d["packet_share"]==23.1, f"packet share {d['packet_share']}")
check(d["air_share"] is not None and 15<d["air_share"]<30, f"air share {d['air_share']}")
check(g.fg_status()["damaged"]["damaged"]==30,"shown in the FloodGuard status")
check(g.stats["unreadable"]<=g.stats["channel_messages"],"sane counters")

# flood share: 30 damaged flood copies in the last five minutes alongside 20 ordinary flood packets
def window(n_good,n_bad,t):
    out=[]
    for i in range(n_good): out.append(gpkt(t-290+i*3, enc("Z%d"%i,"x"), hops=2, length=60))
    for i in range(n_bad): out.append(gpkt(t-290+i*3+1, damage(enc("Z%d"%i,"x")), hops=2, length=60))
    return out
g2=guard(mock()); g2.radio=dict(RADIO); g2.refresh_openhop_info=lambda *a,**k: None
t=time.time(); g2.ingest(window(80,10,t)); busy,share,n=g2.fg_load(t)
check(share>0.95 and n==90-10,f"a few damaged copies are set aside entirely: share {share:.2f} n {n}")
# all damage: nothing but damaged copies must not hide a flood. Capped at a quarter of the airtime, the rest is flood.
g3=guard(mock()); g3.radio=dict(RADIO); g3.refresh_openhop_info=lambda *a,**k: None
g3.ingest(window(0,100,t)); busy,share,n=g3.fg_load(t)
check(share>=0.6 and n>=60,f"junk with a bad check still counts as a flood: share {share:.2f} n {n}")
# direct packets don't turn damaged copies into more than they are
check(g3._dmg_share>0.9,"the damaged share of the airtime is reported as it is")

# ---- dropping damaged copies: off by default, Public only, flood packets only, never without the rule-check fix
class PK:
    def __init__(s,hexs,ptype=5): s.payload=bytearray(bytes.fromhex(hexs)); s.path=["69"]; s.transport_codes=[0,0]; s.pt=ptype
    def get_path_hashes_hex(s): return s.path
    def get_payload_type(s): return s.pt
    def get_payload(s): return s.payload
def verdict(rules, hexs, route=1):
    pe={"enabled":True,"default_action":"allow","rules":rules,"objects":{}}
    return PolicyEngine(pe).evaluate(PK(hexs),{"route_type":route,"payload_type":5,"hop_count":2,"local_transmission":False}).action
g4=guard(mock()); g4.refresh_openhop_info=lambda *a,**k: None
g4.apply_settings({"mode":"protect"})
check(g4._build_damaged()==[],"off by default: no rule")
g4.apply_settings({"drop_damaged":True})
r=g4._build_damaged()
check(len(r)==1 and r[0]["then"]["action"]=="drop","on in Protect: one drop rule")
check(verdict(r,good)=="allow","a good Public packet passes")
check(verdict(r,damage(good))=="drop","a damaged Public flood packet is not passed on")
check(verdict(r,damage(good),route=2)=="allow","a direct packet is never touched")
check(verdict(r,other.hex())=="allow","a packet on another channel code is never touched")
rid=g4._build_damaged()[0]["id"]
check(rid in g4.damaged_rule_ids(),"its stops are counted")
g4.apply_settings({"mode":"monitor"})
check(g4._build_damaged()[0]["then"]["action"]=="log_only","in Monitor it only logs")
g4.apply_settings({"mode":"protect"})
g4.openhop_rulecheck_fix=lambda: False
check(g4._build_damaged()==[],"without the openHop rule-check fix the rule is not written")
check("drop_damaged" not in sg.profile_keys(),"not part of a settings profile")
check(any(m["key"]=="drop_damaged" for m in sg.SETTINGS_META),"shown as a setting with its risk")

# ---- coding rate shown for the FloodGuard page's note
g5=guard(mock()); g5.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":5,"preamble_length":16}
check(g5.coding_rate()==5 and g5.fg_status()["coding_rate"]==5,"coding rate 4/5 is reported")
g5.radio["coding_rate"]=8
check(g5.fg_status()["coding_rate"]==8,"coding rate 4/8 is reported")
g5.radio={}
check(g5.coding_rate() is None,"unknown when openHop hasn't said")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
