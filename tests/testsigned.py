# Signed channel messages: SpamGuard can count them, check each signature against the sender's advertised key,
# suggest trusting a known person's key, and exempt a correctly signed message from that key from spam rules.
# It never holds anything back for being signed, unsigned or failing the check. Keys, names and texts are made up.
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
    ct=AES.new(k[:16],AES.MODE_ECB).encrypt(pt)
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

priv,pub=newkey()
# the trailer is recognised, and plain messages are not mistaken for one
payload=bytes.fromhex(signed_payload(priv,"Quarry Pete","Morning all from the hill"))
d=sg.decrypt_group_text(payload,{"Public":KEY})
check(d and d["sender"]=="Quarry Pete" and d["text"]=="Morning all from the hill", "the visible message is unchanged by the trailer")
check(d and d.get("signed") and d["signed"]["kid"]==pub[:8].hex().upper() and len(d["signed"]["sig"])==64, "the trailer's key id and signature are read")
check(sg.verify_signed(pub,d["signed"]["sig"],d["signed"]["cover"])=="ok", "a correct signature verifies")
tam=sg.decrypt_group_text(bytes.fromhex(signed_payload(priv,"Quarry Pete","Morning all",tamper=True)),{"Public":KEY})
check(sg.verify_signed(pub,tam["signed"]["sig"],tam["signed"]["cover"])=="bad", "a changed message does not verify")
check(sg.verify_signed(None,d["signed"]["sig"],d["signed"]["cover"])=="unknown", "no key: unknown, not failed")
plain=sg.decrypt_group_text(bytes.fromhex(enc("Quarry Pete","Morning all")),{"Public":KEY})
check(plain and "signed" not in plain, "an ordinary message has no trailer")
check(sg.split_signed(b"\x00"*5+b"hello"+sg.SIGNED_MARK+b"\x01"*10+b"\x00"*16) is None, "a marker too close to the end is not a trailer")

check(sg.DEFAULT_CONFIG["signed_watch"] is False and sg.META_BY_KEY["signed_watch"]["type"]=="bool", "off by default")

# off: nothing is counted
m=mock(); g=guard(m, known_min_msgs=2)
for i in range(3): add_signed(m,priv,"Quarry Pete",f"Morning {i}",ago=600-i*60)
run(g)
check(not g.signed_stats and not g.status()["signed"]["on"], "off: nothing counted, nothing shown")

# on: counted and checked against the advert
m=mock(); g=guard(m, known_min_msgs=2, signed_watch=True); g.apply_settings({"mode":"protect"})
add_advert(m,pub,"Quarry Pete")
for i in range(2): m.add("Quarry Pete",f"Nice and clear {i}",["4C","2F"],ago=3000-i*60)   # becomes known
add_signed(m,priv,"Quarry Pete","Morning one",ago=600)
add_signed(m,priv,"Quarry Pete","Morning two",ago=500)
_,priv2=None,None
other,_o=newkey()
add_signed(m,other,"Stranger Sam","Hello there",ago=400)     # no advert heard for this key
add_signed(m,priv,"Quarry Pete","Morning three, changed",ago=300,tamper=True)
run(g)
s=g.status()["signed"]
check(s["on"] and s["today"]["n"]==4, f"four signed messages counted: {s['today']}")
check(s["today"]["ok"]==2 and s["today"]["bad"]==1 and s["today"]["unk"]==1, f"two correct, one not matching, one unchecked: {s['today']}")
check(s["today"]["signers"]==2, "two different signers")
check(not g.signer_suggest, "two correct messages is not yet enough to suggest")
check(not g.blocks, "signatures never create a block")
add_signed(m,priv,"Quarry Pete","Morning four",ago=100)
run(g)
sug=g.status()["signer_suggestions"]
check(len(sug)==1 and sug[0]["name"]=="Quarry Pete" and sug[0]["kid"]==pub[:8].hex().upper(), f"a known person's third correct message suggests trusting the key: {sug}")
check(not g.signer_bind, "a suggestion trusts nothing by itself")

# two keys signing as the same name: neither is suggested
m2=mock(); g3=guard(m2, known_min_msgs=2, signed_watch=True); g3.apply_settings({"mode":"protect"})
pa,pubA=newkey(); pb,pubB=newkey()
add_advert(m2,pubA,"Quarry Pete"); add_advert(m2,pubB,"Quarry Pete")
for i in range(2): m2.add("Quarry Pete",f"Nice and clear {i}",["4C","2F"],ago=3000-i*60)
for i in range(3): add_signed(m2,pa,"Quarry Pete",f"Real one {i}",ago=600-i*50)
for i in range(3): add_signed(m2,pb,"Quarry Pete",f"Copy {i}",ago=400-i*50)
run(g3)
check(not g3.signer_suggest, "a name signed by two different keys is never suggested")

# the stranger's key is never suggested (not a known name)
check(all(x["name"]!="Stranger Sam" for x in sug), "a name SpamGuard doesn't know gets no suggestion")

kid=pub[:8].hex().upper()
g.action("accept_signer",{"kid":kid})
check(g.signer_bind.get(kid)=="Quarry Pete" and not g.signer_suggest, "accepting trusts the key as that person")
add_signed(m,priv,"Quarry Pete","Morning five",ago=50)
run(g)
ev=[e for e in g.events if e.text=="Morning five"]
check(ev and ev[0].exempt, "a correctly signed message from the trusted key is exempt from spam rules")
add_signed(m,priv,"Somebody Else","Pretending to be another name",ago=40)
run(g)
ev=[e for e in g.events if e.text=="Pretending to be another name"]
check(ev and not ev[0].exempt, "the trusted key is only trusted as the name you accepted")
add_signed(m,priv,"Quarry Pete","Altered after signing",ago=30,tamper=True)
run(g)
ev=[e for e in g.events if e.text.startswith("Altered after signing")]
check(ev and not ev[0].exempt, "a message that does not verify is not exempt")

# airtime line: signatures show up in the hour's record
g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
check(any(h.get("sg") for h in g.hist.values()), "signed packets are counted in the hourly record")

g.action("unbind_signer",{"kid":kid})
check(not g.signer_bind, "trust can be taken back")
g.action("accept_signer",{"kid":kid}) if False else None
g.signer_suggest[kid]={"name":"Quarry Pete","n":3}
g.action("dismiss_signer",{"kid":kid})
check(not g.signer_suggest and g.suppressed.get("signer:"+kid,0)>time.time(), "Not now hides it for a week")

# trusted keys and the counts survive a restart
g.signer_bind[kid]="Quarry Pete"; g._save_state(force=True)
g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.signer_bind.get(kid)=="Quarry Pete" and g2.signed_stats, "trusted keys and counts are saved")
check("pub" not in json.dumps(g2.status()["signed"]) and "sig" not in json.dumps(g2.status()["signer_suggestions"]), "no keys or signatures in the summary")

# the page
ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check('id="signedSec"' in ui and "renderSigned" in ui and "/accept_signer" in ui, "the page has the Signed messages section")
check({"accept_signer","dismiss_signer","unbind_signer"} <= sg.ACTIONS, "the actions are allowed")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
