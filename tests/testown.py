# The repeater's own companions (openHop identities) are never blocked: SpamGuard learns their names and IDs
# from openHop, leaves their messages (no path) out of its detection, and every SpamGuard rule in openHop
# skips messages the repeater sends itself. A far-away sender using the same name is not exempt.
# All names and keys are made up.
import sys, logging, time
from harness import *
from repeater.policy_engine import PolicyEngine
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
real=g._api
IDS={"success":True,"data":{"registered":[],"configured":[],"configured_companions":[
    {"name":"HomeCompanion","type":"companion","settings":{"node_name":"Garden Shed 🐀"},"public_key":"a1b2c3d4e5f60718293a4b5c6d7e8f90","hash":"0xA1"}]}}
def api(method, path, body=None, timeout=None):
    if path=="/api/identities": return IDS
    return real(method, path, body, timeout=timeout) if timeout else real(method, path, body)
g._api=api
g.refresh_own_identities(force=True)
check("Garden Shed 🐀" in g.own_names and g.own_names["Garden Shed 🐀"]["id"]=="A1B2C3D4E5F6","learns own companion name and ID: "+str(g.own_names))
st=g.status()
check(len(st["own"])==1 and "Garden Shed 🐀" in st["own"][0]["names"] and "HomeCompanion" in st["own"][0]["names"] and st["own"][0]["id"]=="A1B2C3D4E5F6","page lists each own companion once, with its names and ID: "+str(st["own"]))
# own companion repeats itself (sent here: no path) -> no repeat block
for i in range(8): m.add("Garden Shed 🐀","Testing my new companion setup again",[],ago=200-i*10)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(not any(b["kind"]=="repeat" for b in g.blocks.values()),"own companion repeating itself is not blocked")
own_ev=[e for e in g.events if e.sender=="Garden Shed 🐀"]
check(own_ev and all(g.is_own(e) and e.matched is None for e in own_ev),"own messages never counted as caught")
# someone far away using the same name, repeating: still caught
for i in range(6): m.add("Garden Shed 🐀","Fake one repeating this line",["9D","4C"],ago=100-i*10)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(any(b["kind"]=="repeat" for b in g.blocks.values()),"same name from elsewhere is still caught")
# every SpamGuard drop rule skips local transmissions, in openHop's real policy engine
rules=g.build_rules()
drops=[r for r in rules if r["then"]["action"]=="drop"]
check(drops and all(any(c.get("field")=="local_transmission" for c in r["if"]["all"]) for r in drops),"every drop rule skips the repeater's own messages")
pe=PolicyEngine(m.policy["policy_engine"])
class P:
    def __init__(s,sender,text,path): s.payload=bytearray(bytes.fromhex(enc(sender,text,sg.PUBLIC_CHANNEL_KEY))); s.transport_codes=[0,0]; s.path=path
    def get_path_hashes_hex(s): return s.path
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
check(PolicyEngine(m.policy["policy_engine"]).evaluate(P("Garden Shed 🐀","Fake one repeating this line",["9D","4C"]),{"payload_type":5,"local_transmission":False}).action=="drop","received copy is dropped")
check(PolicyEngine(m.policy["policy_engine"]).evaluate(P("Garden Shed 🐀","Fake one repeating this line",[]),{"payload_type":5,"local_transmission":True}).action=="allow","the repeater's own send is never dropped")
check(PolicyEngine(m.policy["policy_engine"]).evaluate(P("Garden Shed 🐀","Fake one repeating this line",["9D"]),{"payload_type":5}).action=="drop","older openHop without the flag: rule still works")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
