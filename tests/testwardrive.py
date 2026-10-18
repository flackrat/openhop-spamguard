# "Don't repeat wardriving pings": off by default; when on, pings on the wardriving channel aren't passed on,
# everything else is, and this repeater's own companions' pings still go out. Checked against openHop's own
# rule engine. All names, places and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

WD=sg.hashtag_secret("#wardriving")
class P:
    def __init__(s, key, text):
        s.payload=bytearray(bytes.fromhex(enc("Van 3",text,key))); s.transport_codes=[0,0]
    def get_path_hashes_hex(s): return ["4C"]
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m, key, text, local=False):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(key,text),{"payload_type":5,"hop_count":1,"route_type":1,
        "local_transmission":local}).action
PING="@[MapperBot]<51.70210 0.02790> 22"
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()

m=mock(); g=guard(m, floodguard=False); sync(g)
check(not g.cfg["wardrive_block"],"off by default")
check(act(m,WD,PING)=="allow","pings are repeated by default")
g.apply_settings({"wardrive_block":True}); sync(g)
check(act(m,WD,PING)=="drop","on: a wardriving ping isn't repeated")
check(act(m,WD,PING,local=True)=="allow","a ping from this repeater's own companion still goes out")
check(act(m,sg.PUBLIC_CHANNEL_KEY,"Morning all, clear skies on the hill")=="allow","Public messages are untouched")
check(act(m,sg.hashtag_secret("#chat"),"Anyone about tonight?")=="allow","other hashtag channels are untouched")
check(act(m,sg.PUBLIC_CHANNEL_KEY,PING)=="allow","even a ping-looking message on Public goes out")
r=[x for x in m.policy["policy_engine"]["rules"] if "wardriving" in x["name"]]
check(len(r)==1 and r[0]["then"]["action"]=="drop","one rule, blocking")
g.apply_settings({"mode":"monitor"}); sync(g)
check(act(m,WD,PING)=="log_only","Monitor: only logged")
g.apply_settings({"mode":"protect"})

# a channel sharing the one-byte channel code: only ping-looking messages are held back there
hb=sg.channel_hash_byte(WD); i=0
while True:
    i+=1; nm=f"#clash{i}"
    if sg.channel_hash_byte(sg.hashtag_secret(nm))==hb: break
g.action("add_channel",{"name":nm}); sync(g)
check(nm in "".join(g.cfg["channels"]) and "#wardriving" in g.wardrive_collisions(),f"spots the shared channel code ({nm})")
check(act(m,sg.hashtag_secret(nm),"Chat on a channel that happens to share the code")=="allow","chat on the clashing channel still goes out")
check(act(m,WD,PING)=="drop","pings are still held back")
MM="MM:1BA-UDlxKQ"   # how MeshRank shows current MeshMapper pings (6.4.3)
check(act(m,WD,MM)=="drop","on a clashing channel, the MM: form is held back too")
check(act(m,sg.hashtag_secret("#chat"),MM)=="allow","an MM: message on an unrelated channel is not touched")

# one fixed channel: no setting for others, and a saved list from an older version is ignored
check("wardrive_channels" not in [m["key"] for m in sg.SETTINGS_META],"no channel list setting")
check(list(g.wardrive_channels())==["#wardriving"],"only #wardriving is covered")
check(act(m,sg.hashtag_secret("#wardrive"),PING)=="allow","an old extra channel is no longer covered")

# counting
rid=g.rule_ids[f"wardrive:{WD}"]
now=time.time()
g.ingest([{"id":"w1","timestamp":now+1,"type":5,"route":1,"length":60,"rssi":-90,"snr":3,"transmitted":False,
           "payload":enc("Van 3",PING,WD),"original_path":"[\"4C\"]","drop_reason":f"Policy blocked packet (rule {rid})"}])
d1=g.metrics()["d1"]; w=g.metrics()["wardrive"]
check(d1["ws"]==1 and d1["wh"]>=1,"pings not repeated are counted")
check(w["enabled"] and rid in w["rules"],"status says it's on")

# a privacy choice: kept when everything is reset, never in a settings profile
g.reset_all()
check(g.cfg["wardrive_block"],"kept through Start again from scratch")
check("wardrive_block" not in sg.profile_keys(),"not part of settings profiles")
g.apply_settings({"wardrive_block":False}); sync(g)
check(act(m,WD,PING)=="allow","off again: pings are repeated")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
