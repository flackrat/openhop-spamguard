# A name you have tied to a signing key only gets that person's trust when the message carries their signature.
# An unsigned copy of the name is treated as a stranger, and held from repeaters the person never uses. Their own
# unsigned messages from their usual way in are left alone. Keys, names and texts are made up.
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


# --- A name tied to a signing key only gets that person's trust when the message carries their signature
priv,pub=newkey(); kid=pub[:8].hex().upper()
m=mock(); g=guard(m, signed_watch=True, known_min_msgs=2); g.apply_settings({"mode":"protect"})
add_advert(m,pub,"Signed Sally",ago=5000)
for i in range(6):
    add_signed(m,priv,"Signed Sally",f"Evening all, chat number {i}",path=("A1","B2"),ago=4000-i*500)
run(g); run(g)
kid=next(iter(g.signer_keys)) if g.signer_keys else kid
g.signer_bind[kid]="Signed Sally"
check(g.is_known("Signed Sally"), "Sally is known and her key is trusted")
check(sum(g.homes.get("Signed Sally",{}).values())>=5, "her usual way in is remembered")
# a gated block is in place (a repeater block that lets known people through)
g._add_block("hop:D9","hop","D9","test block on D9","manual",ttl=3600)
for b in g.blocks.values(): b["created"]=time.time()-5000
add_signed(m,priv,"Signed Sally","The real me, signed, via D9",path=("D9","E6"),ago=300)
m.add("Signed Sally","A copy of my name, unsigned, via D9",["D9","E6"],ago=290)
m.add("Signed Sally","Unsigned from my usual way in",["A1","B2"],ago=280)
m.add("Signed Sally","Unsigned from a new place",["F4","E6"],ago=270)
run(g); run(g)
ev={e.text:e for e in g.events}
check(not ev["The real me, signed, via D9"].matched, "her signed message gets through the block")
check(ev["A copy of my name, unsigned, via D9"].unverified and ev["A copy of my name, unsigned, via D9"].matched, "an unsigned copy of her name does not get her trust, so the block applies")
check(ev["Unsigned from my usual way in"].unverified and not ev["Unsigned from my usual way in"].matched, "unsigned from her usual way in is noted, not held (it may be her on another device)")
ib=[b for b in g.blocks.values() if b["kind"]=="imposter"]
check(any(b.get("who")=="Signed Sally" and b["value"]=="F4" for b in ib), f"openHop is told to hold her name from the new place: {[(b.get('who'),b['value']) for b in ib]}")
check(not any(b["value"]=="A1" for b in ib), "never from her usual way in")
check("F4" not in g.homes.get("Signed Sally",{}), "unsigned copies don't teach SpamGuard a new home for her")
# names without a trusted key are unaffected, and with signed checking off nothing changes
check(not any(e.unverified for e in g.events if e.sender!="Signed Sally"), "nobody else is marked")
g.cfg["signed_watch"]=False
m.add("Signed Sally","With checking off",["A1","B2"],ago=100); run(g)
check(not [e for e in g.events if e.text=="With checking off"][0].unverified, "with signed checking off, nothing changes")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
