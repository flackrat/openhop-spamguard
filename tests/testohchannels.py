# Channels openHop's policy settings already name are offered on the page (names only, never keys),
# can be added with one press (one or several at once), and drop out of the offer once SpamGuard reads
# them. Each block shows the openHop rule numbers that openHop's packet feed mentions.
# All channel names and keys are made up.
import sys, logging, hashlib
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def key(n): return hashlib.sha256(n.encode()).hexdigest()[:32]
m=mock()
m.policy["policy_engine"].setdefault("objects",{})["channels"]={
    "Wandelclub":key("w"), "Fietsers":{"secret":key("f")}, "broken":"not-a-key", "Public":sg.PUBLIC_CHANNEL_KEY}
g=guard(m); g.apply_settings({"mode":"protect"})
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
st=g.status()
check(st.get("channel_choices")==["Fietsers","Wandelclub"],"openHop's named channels offered, already-read and bad keys left out: "+str(st.get("channel_choices")))
check(key("w") not in json.dumps(st),"keys never sent to the page")
g.action("add_openhop_channel",{"name":"Wandelclub"})
st=g.status()
check("Wandelclub" in st["channels"] and st["channel_choices"]==["Fietsers"],"added, and no longer offered")
check(g.cfg["channels"]["Wandelclub"]==key("w"),"key taken from openHop")
try:
    g.action("add_openhop_channel",{"name":"Nergens"}); check(False,"unknown channel refused")
except ValueError: check(True,"")
# list form, several at once
m2=mock()
m2.policy["policy_engine"].setdefault("objects",{})["channels"]=[{"name":"A-team","key":key("a")},{"name":"B-team","psk":key("b")}]
g2=guard(m2); g2.poll_once(); g2.last_sync=0; g2.sync_pending=True; g2.poll_once()
g2.action("add_openhop_channel",{"names":["A-team","B-team"]})
check({"A-team","B-team"}<=set(g2.status()["channels"]),"several added in one go")
# rule numbers per block
g.action("block_text",{"text":"cheap antennas here"})
g.last_sync=0; g.sync_pending=True; g.poll_once()
b=[x for x in g.status()["blocks"] if x["kind"]=="text"][0]
ids={r["id"] for r in m.policy["policy_engine"]["rules"] if "cheap antennas" in r.get("name","")}
check(b["rules"] and set(b["rules"])==ids,"block shows the openHop rule number(s): "+str(b["rules"])+" "+str(ids))
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
