# "Keep bots off Public": opt-in, and only counting at first. Counted offline from what the repeater hears;
# when switched to stopping, three rules drop bot commands and bot replies on Public only. Checked against
# openHop's own rule engine. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
class P:
    def __init__(s, key, text, sender="Van 3"):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,key))); s.transport_codes=[0,0]
    def get_path_hashes_hex(s): return ["4C"]
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m, key, text, local=False):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(key,text),{"payload_type":5,"hop_count":1,"route_type":1,
        "local_transmission":local}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
PUB=sg.PUBLIC_CHANNEL_KEY
ACK="@[Sam], ack: SNR 12.0 dB, RSSI -52 dBm, 9 hops via 4E, B7, 9C"
RX="@[Sam] RX 12h57m | Mossbrook | Hops:11 | Path:33>98>72"
CMD="!ping"
HUMAN="@[Sam] 23 hops to Harrowfield, lovely morning"

# 1. Off by default: nothing counted, no rules
m=mock(); g=guard(m, floodguard=False)
for t in (ACK,RX,CMD): m.add("Bot1",t,["4C"],ago=60)
sync(g)
check(g.cfg["public_bots"] is False and g.cfg["public_bots_log_only"] is True,"off, and count-only, by default")
check(g.status()["summary"]["pubbots_mode"]=="off" and g.status()["summary"]["pubbots_24h"]==0,"off: nothing counted")
check(not [r for r in m.policy["policy_engine"]["rules"] if "bots on Public" in r["name"]],"off: no rules")

# 2. On, count only: counted, nothing stopped, no rules
m=mock(); g=guard(m, floodguard=False, public_bots=True, dedupe_enabled=False, repeat_guard=False)
for i,t in enumerate((ACK,RX,CMD,HUMAN)): m.add(f"Node {i}",t,["4C"],ago=60-i)
m.add("Node 9",ACK,["4C"],ago=30,key=sg.hashtag_secret("#test"))
g.apply_settings({"mode":"protect"}); sync(g)
sm=g.status()["summary"]
check(sm["pubbots_24h"]==3,"three bot-shaped messages on Public counted; the human one and the #test one are not")
check(sm["pubbots_mode"]=="count","mode says count")
check(not [r for r in m.policy["policy_engine"]["rules"] if "bots on Public" in r["name"]],"count only: no rules written")
check(act(m,PUB,ACK)=="allow","count only: the bot reply is still passed on")

# 3. Stopping: rules drop the shapes on Public only
g.apply_settings({"public_bots_log_only":False}); sync(g)
rs=[r for r in m.policy["policy_engine"]["rules"] if "bots on Public" in r["name"]]
check(len(rs)==3 and all(r["then"]["action"]=="drop" for r in rs),"three rules, dropping")
check(act(m,PUB,ACK)=="drop" and act(m,PUB,RX)=="drop" and act(m,PUB,CMD)=="drop","all three shapes dropped on Public")
check(act(m,PUB,HUMAN)=="allow","a person talking about hops is passed on")
check(act(m,PUB,"Morning all, clear skies today")=="allow","ordinary Public chat is passed on")
check(act(m,sg.hashtag_secret("#test"),ACK)=="allow" and act(m,sg.hashtag_secret("#bot"),CMD)=="allow","other channels are never touched")
check(act(m,PUB,ACK,local=True)=="allow","this repeater's own companion is never stopped")
check(g.status()["summary"]["pubbots_mode"]=="stop","mode says stop")

# 4. Monitor only logs
g.apply_settings({"mode":"monitor"}); sync(g)
check(act(m,PUB,ACK)=="log_only","Monitor: logged, not dropped")

# 5. Switching it off again takes the rules away
g.apply_settings({"mode":"protect","public_bots":False}); sync(g)
check(not [r for r in m.policy["policy_engine"]["rules"] if "bots on Public" in r["name"]],"off again: rules gone")
check(sg.bot_shaped("!test") and not sg.bot_shaped("test") and not sg.bot_shaped("my SNR is fine"),"shape tests")
check(sg.bot_shaped("SNR 3 and RSSI -90"),"both words needed, either order")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
