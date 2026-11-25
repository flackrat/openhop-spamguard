# Reading Sigstore's published keys (only needed when Sigstore changes them) is checked the way TUF requires:
# root changes signed by enough old and new key holders, every file signed by the keys the root names, nothing
# expired or older than seen before, and the key list matching its signed checksums. A made-up update repository
# with throwaway keys; Sigstore's real root history (versions 1 to 16) was checked the same way when this was built.
import sys, os, json, hashlib, copy, logging
from harness import *
logging.disable(logging.WARNING)
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:
    print("cryptography not installed: skipped"); sys.exit(0)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
NOW=1800000000; FUT="2030-01-01T00:00:00Z"; PAST="2020-01-01T00:00:00Z"
def key():
    k=ec.generate_private_key(ec.SECP256R1())
    pem=k.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return k,hashlib.sha256(pem.encode()).hexdigest(),{"keytype":"ecdsa","scheme":"ecdsa-sha2-nistp256","keyval":{"public":pem}}
def sign(signed,keys):
    data=sg.canonical_json(signed)
    return {"signed":signed,"signatures":[{"keyid":kid,"sig":k.sign(data,ec.ECDSA(hashes.SHA256())).hex()} for k,kid,_ in keys]}
R=[key() for _ in range(5)]; TS=key(); SN=key(); TG=[key() for _ in range(3)]
def root(v,rk,expires=FUT,ts=TS):
    ks={kid:pub for _,kid,pub in rk+[ts,SN]+TG}
    return {"_type":"root","spec_version":"1.0","version":v,"expires":expires,"consistent_snapshot":True,"keys":ks,
            "roles":{"root":{"keyids":[k[1] for k in rk],"threshold":3},"timestamp":{"keyids":[ts[1]],"threshold":1},
                     "snapshot":{"keyids":[SN[1]],"threshold":1},"targets":{"keyids":[k[1] for k in TG],"threshold":2}}}
TRUSTED=json.dumps({"certificateAuthorities":[],"tlogs":[]}).encode()
def repo(ts_spec="1.0",ts_v=7,sn_v=5,tg_v=3,ts_exp=FUT,ts_key=None,tg_keys=None,trusted=TRUSTED,tg_tamper=False,sn_hash=False,roots=None):
    tgs={"_type":"targets","spec_version":"1.0","version":tg_v,"expires":FUT,"targets":{"trusted_root.json":{"length":len(TRUSTED),"hashes":{"sha256":hashlib.sha256(TRUSTED).hexdigest()}}}}
    tg=sign(tgs,tg_keys or TG[:2])
    if tg_tamper: tg["signed"]["targets"]["trusted_root.json"]["length"]+=0; tg["signed"]["expires"]="2031-01-01T00:00:00Z"
    tgraw=json.dumps(tg).encode()
    sn=sign({"_type":"snapshot","spec_version":"1.0","version":sn_v,"expires":FUT,"meta":{"targets.json":{"version":tg_v}}},[SN]); snraw=json.dumps(sn).encode()
    smeta={"version":sn_v}
    if sn_hash: smeta.update(length=len(snraw),hashes={"sha256":"0"*64})
    ts=sign({"_type":"timestamp","spec_version":ts_spec,"version":ts_v,"expires":ts_exp,"meta":{"snapshot.json":smeta}},[ts_key or TS])
    files={"timestamp.json":json.dumps(ts).encode(),f"{sn_v}.snapshot.json":snraw,f"{tg_v}.targets.json":tgraw,
           f"targets/{hashlib.sha256(TRUSTED).hexdigest()}.trusted_root.json":trusted}
    files.update(roots or {})
    return lambda u: files.get(u.split("sigstore.dev/",1)[1])
real_root=sg.SIGSTORE_TUF_ROOT
sg.SIGSTORE_TUF_ROOT=root(1,R)
def F(get,seen=None):
    try: return sg.fetch_sigstore_root(get,seen=seen,now=NOW)
    except ValueError as e: return str(e)
r=F(repo()); check(isinstance(r,tuple) and r[1]=={"root":None,"timestamp":7,"snapshot":5,"targets":3},"a properly signed repository is read: %s"%(r if isinstance(r,str) else r[1]))
# root changes
R2=[key() for _ in range(5)]; TS2=key()
v2=root(2,R2,ts=TS2)
good2=sign(v2,R[:3]+R2[:3])
r=F(repo(ts_key=TS2,roots={"2.root.json":json.dumps(good2).encode()}))
check(isinstance(r,tuple) and r[1]["root"]["version"]==2,"a new root signed by enough old and new key holders is followed, and its keys used")
r=F(repo(ts_key=TS2,roots={"2.root.json":json.dumps(sign(v2,R2[:3])).encode()}))
check(isinstance(r,str) and "key holders" in r,"a new root signed only by its own keys is refused")
r=F(repo(ts_key=TS2,roots={"2.root.json":json.dumps(sign(v2,R[:3]+R2[:2])).encode()}))
check(isinstance(r,str),"a new root without enough of its own key holders is refused")
r=F(repo(ts_key=TS2,roots={"2.root.json":json.dumps(sign(root(3,R2,ts=TS2),R[:3]+R2[:3])).encode()}))
check(isinstance(r,str) and "version" in r,"a root that skips a version is refused")
r=F(repo(roots={"2.root.json":json.dumps(sign(root(2,R,expires=PAST),R[:3])).encode()}))
check(isinstance(r,str) and "expired" in r,"an expired newest root is refused")
# the other files
check(isinstance(F(repo(ts_key=key())),str),"a timestamp signed by another key is refused")
check(isinstance(F(repo(tg_keys=TG[:1])),str),"targets signed by fewer than the threshold are refused")
check(isinstance(F(repo(tg_keys=[TG[0],TG[0]])),str),"the same key twice doesn't count as two")
check(isinstance(F(repo(tg_tamper=True)),str),"a targets file changed after signing is refused")
check(isinstance(F(repo(sn_hash=True)),str),"a snapshot that doesn't match its listed checksum is refused")
check(isinstance(F(repo(trusted=TRUSTED+b" ")),str),"a key list that doesn't match its signed checksum is refused")
check(isinstance(F(repo(ts_exp=PAST)),str),"an expired timestamp is refused")
r=F(repo(ts_spec="2.0")); check(isinstance(r,str) and "format" in r,"a file in a TUF format this version doesn't know is refused")
# rollback
r=F(repo(ts_v=7),seen={"timestamp":9,"snapshot":5,"targets":3}); check(isinstance(r,str) and "older" in r,"an older timestamp than seen before is refused")
r=F(repo(sn_v=4,ts_v=10),seen={"timestamp":9,"snapshot":5,"targets":3}); check(isinstance(r,str),"an older snapshot than seen before is refused")
r=F(repo(tg_v=2,sn_v=6,ts_v=10),seen={"timestamp":9,"snapshot":5,"targets":3}); check(isinstance(r,str),"older targets than seen before are refused")
r=F(repo(ts_key=TS2),seen={"root":v2,"timestamp":1,"snapshot":1,"targets":1}); check(isinstance(r,tuple),"a newer root trusted before is the starting point")
# the updater remembers what it trusted, and hands it back next time
g=guard(mock()); calls=[]
real_fetch=sg.fetch_sigstore_root
sg.fetch_sigstore_root=lambda seen=None,**k: calls.append(seen) or ({"cas":[],"logs":{}},{"root":None,"timestamp":7,"snapshot":5,"targets":3})
g._sigstore_root(); check(g.sigstore_seen["timestamp"]==7,"what was trusted is remembered")
g._sigstore_cache=None; g._sigstore_root(); check(calls[-1]["timestamp"]==7,"and given back the next time")
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg)); check(g2.sigstore_seen.get("timestamp")==7,"across a restart")
sg.fetch_sigstore_root=real_fetch; sg.SIGSTORE_TUF_ROOT=real_root
# canonical form as TUF signs it: only quote and backslash escaped
check(sg.canonical_json({"b":"x\ny","a":[1,True,None],"c":'q"\\'})==b'{"a":[1,true,null],"b":"x\ny","c":"q\\"\\\\"}',"canonical JSON matches TUF's")
check(real_root["version"]>=16 and "@" not in json.dumps(real_root).replace("-----BEGIN",""),"the built-in root carries keys only, no names")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
