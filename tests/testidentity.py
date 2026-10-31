# Each message shows how far its sender's identity can be trusted: signed by a key you trust, a name you tied
# to a key but without the signature, a name SpamGuard knows (which anyone can copy), or unknown. Keys, names
# and texts are made up.
import sys, logging
from harness import *
from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

KEY=sg.PUBLIC_CHANNEL_KEY
def newkey():
    k=ECC.generate(curve="Ed25519"); return k, k.public_key().export_key(format="raw")
def signed_payload(priv, sender, text, tamper=False, ts=None):
    k=sg._secret32(KEY); ts=(ts or int(time.time())).to_bytes(4,"little")
    body=f"{sender}: {text}".encode()
    bind=hashlib.sha256(bytes.fromhex(KEY)[:16] if len(bytes.fromhex(KEY))>=16 else bytes.fromhex(KEY)).digest()[:16]
    sig=eddsa.new(priv,"rfc8032").sign(sg.SIGNED_LABEL+bind+ts+body)
    pub=priv.public_key().export_key(format="raw")
    shown=f"{sender}: {text}x".encode() if tamper else body
    pt=ts+b"\x00"+shown+sg.SIGNED_MARK+pub[:8]+sig
    pt+=b"\x00"*((-len(pt))%16)
    # MeshCore encrypts each 16-byte block on its own; one block at a time with a zero start value is the same thing
    ct=b"".join(AES.new(k[:16],AES.MODE_CBC,iv=b"\x00"*16).encrypt(pt[i:i+16]) for i in range(0,len(pt),16))
    return (bytes([sg.channel_hash_byte(KEY)])+hmac.new(k,ct,hashlib.sha256).digest()[:2]+ct).hex()
def advert_payload(pub, name):
    return (pub+b"\x00"*4+b"\x00"*64+bytes([0x82])+name.encode()+b"\x00").hex()
def add_signed(m, priv, sender, text, path=("4C","2F"), ago=0, **kw):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":5,"payload":signed_payload(priv,sender,text,**kw),
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(list(path))})
def add_advert(m, pub, name, ago=900):
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":4,"payload":advert_payload(pub,name),
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(["4C"])})
def run(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()

priv,pub=newkey(); kid=pub[:8].hex().upper()
m=mock(); g=guard(m, known_min_msgs=2, signed_watch=True); g.apply_settings({"mode":"protect"})
add_advert(m,pub,"Quarry Pete")
for i in range(2): m.add("Quarry Pete",f"Nice and clear {i}",["4C","2F"],ago=3000-i*60)   # becomes known by name
run(g)
g.signer_bind[kid]="Quarry Pete"
add_signed(m,priv,"Quarry Pete","Signed morning",ago=200)
m.add("Quarry Pete","Same name, no signature",["4C","2F"],ago=150)
m.add("Canal Boat Ted","Out on the lock",["4C","2F"],ago=140)
m.add("Canal Boat Ted","Still on the lock",["4C","2F"],ago=130)
m.add("Visitor Vic","First time here",["4C","2F"],ago=120)
run(g)
rows={r["text"]:r["identity"] for r in g.status()["recent"]}
check(rows.get("Signed morning")=="key", f"signed by a trusted key: {rows}")
check(rows.get("Same name, no signature")=="copied", f"the same name without the signature is flagged as copied: {rows}")
check(rows.get("Still on the lock")=="name", f"a known name with no key is name only: {rows}")
check(rows.get("First time here")=="unknown", f"a stranger is unknown: {rows}")

# Borrowed trust and tampering: wearing a trusted repeater's code, or a signature that doesn't match, gives no identity.
m2=mock(); g2=guard(m2, known_min_msgs=2, signed_watch=True); g2.apply_settings({"mode":"protect"})
add_advert(m2,pub,"Quarry Pete")
for i in range(2): m2.add("Quarry Pete",f"Nice and clear {i}",["4C","2F"],ago=3000-i*60)
run(g2)
g2.signer_bind[kid]="Quarry Pete"
g2.allow_senders.add("Lock Keeper Lou")
spam=[rname() for _ in range(4)]
for i,n in enumerate(spam): m2.add(n,f"Cheap upgrades {i}",["4C","2F"],ago=300-i)          # made-up names on a trusted code
add_signed(m2,priv,"Quarry Pete","Altered after signing",tamper=True,ago=100)               # signature no longer matches the text
m2.add("Lock Keeper Lou","Lock is open",["4C","2F"],ago=90)
run(g2)
rows2={r["text"]:r["identity"] for r in g2.status()["recent"]}
check(all(rows2.get(f"Cheap upgrades {i}")=="unknown" for i in range(4)), f"made-up names on a trusted code stay unknown: {rows2}")
check(rows2.get("Altered after signingx")=="copied", f"a message whose text no longer matches its signature is flagged as a copied name: {rows2}")
check(rows2.get("Lock is open")=="name", f"a name you trust but did not key is name only: {rows2}")

ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check("m.identity===" in ui and "Name copied" in ui and "Name only" in ui, "the Messages list shows the identity tags")

print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
