# Device name history: a companion's signed advert ties a name to its device key, so People can show the other
# names a device has used, flag a name used by more than one device, and list names that change. An unsigned or
# wrongly signed advert adds nothing, and a name change keeps the device's history. All names are made up.
import sys, os, json, time, struct, logging
from harness import *
from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def keypair():
    k=ECC.generate(curve="Ed25519"); return k, k.public_key().export_key(format="raw")
def advert(priv, pub, name, ts, bad=False, forge_with=None):
    app=bytes([0x81])+name.encode()
    t=struct.pack("<I",int(ts))
    sig=eddsa.new(forge_with or priv,"rfc8032").sign(pub+t+app)
    if bad: sig=bytes([sig[0]^1])+sig[1:]
    return (pub+t+sig+app).hex()
def add_adv(m, priv, pub, name, ago, **kw):
    ts=time.time()-ago
    m.packets.append({"id":len(m.packets)+1,"timestamp":ts,"type":4,"payload":advert(priv,pub,name,ts,**kw),
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(["4C"])})
def run(g):
    for _ in range(2):
        g.poll_once(); g.last_sync=0; g.sync_pending=True

m=mock(); g=guard(m)
a,apub=keypair(); b,bpub=keypair(); c,cpub=keypair()
for i in range(3): m.add("Juno Marsh",f"Evening all from the reservoir {i}",["4C","2F"],ago=1500-i*60)
m.add("JunoM Mobile","Testing the handheld",["4C","2F"],ago=1100)
m.add("Kip Ferris","Hello from the hill",["5D","2F"],ago=900)
add_adv(m,a,apub,"Juno Marsh",ago=1300)
add_adv(m,a,apub,"JunoM Mobile",ago=1000)       # the same device, renamed
add_adv(m,a,apub,"Juno Marsh",ago=700)         # and back
add_adv(m,b,bpub,"Kip Ferris",ago=650)
add_adv(m,c,cpub,"Kip Ferris",ago=600)         # another device using the same name
x,xpub=keypair()
add_adv(m,a,apub,"Sneaky Name",ago=500,forge_with=x)   # someone else's key can't add a name to Juno's device
add_adv(m,a,apub,"Bad Sig Name",ago=400,bad=True)
run(g)
key=apub.hex().upper()
names=[x[0] for x in g.dev_names.get(key,[])]
check(names==["JunoM Mobile","Juno Marsh"],"one device, two names, newest last: %s"%names)
check("Sneaky Name" not in json.dumps(list(g.dev_names.values())),"an advert signed by another key adds nothing")
check("Bad Sig Name" not in json.dumps(list(g.dev_names.values())),"a broken signature adds nothing")
check(g.device_names("Juno Marsh")=={"also":["JunoM Mobile"],"devices":1},"Juno: also called: %s"%g.device_names("Juno Marsh"))
check(g.device_names("Kip Ferris")["devices"]==2,"Kip: used by two devices")
P=g.people({"show":"renames"})
check(sorted(r["name"] for r in P["rows"])==["Juno Marsh","JunoM Mobile"],"Changes name filter: %s"%[r["name"] for r in P["rows"]])
check(P["counts"]["renames"]==2,"counted")
allp={r["name"]:r for r in g.people({"show":"all","limit":50})["rows"]}
check(allp["Kip Ferris"]["device"]["devices"]==2,"People row shows two devices")
check(allp["Juno Marsh"]["device"]["also"]==["JunoM Mobile"],"People row shows the other name")
# the history survives a restart, and isn't reset by the name change
g._save_state(force=True)
g2=sg.SpamGuard(dict(g.file_cfg, state_file=g.cfg["state_file"]))
check([x[0] for x in g2.dev_names.get(key,[])]==names,"kept across a restart")
# a name change alone doesn't hold anything
check(not any(b for b in g.blocks.values() if "Juno" in json.dumps(b)),"nothing held for changing name")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
