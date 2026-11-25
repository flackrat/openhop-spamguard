# The updater checks GitHub's build record before installing: a provenance naming the file's sha256, made by this
# project's release workflow, signed with the certificate it carries. A missing, changed, wrongly signed or
# other-project record, or one Sigstore's authority and public log didn't vouch for, means it isn't installed.
# Records here are made up, under a made-up authority and log, plus the real public record of 6.49.0.
import sys, os, json, base64, hashlib, datetime, urllib.error, io, logging
from harness import *
logging.disable(logging.WARNING)
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:
    print("cryptography not installed: skipped"); sys.exit(0)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
REPO="quarry-example/openhop-spamguard"; WF=".github/workflows/release.yml"
T0=datetime.datetime(2026,6,1,12,0,0,tzinfo=datetime.timezone.utc); WHEN=int(T0.timestamp())+60
def name(cn): return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME,"example.test"),x509.NameAttribute(NameOID.COMMON_NAME,cn)])
def ca_cert(key,subj,signer,issuer,ca=True):
    return (x509.CertificateBuilder().subject_name(subj).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(T0-datetime.timedelta(days=30)).not_valid_after(T0+datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(signer,hashes.SHA384()))
# a made-up Sigstore: certificate authority (root and intermediate) and a public log
ROOTK=ec.generate_private_key(ec.SECP384R1()); ROOT=ca_cert(ROOTK,name("made-up root"),ROOTK,name("made-up root"))
INTK=ec.generate_private_key(ec.SECP384R1()); INT=ca_cert(INTK,name("made-up intermediate"),ROOTK,name("made-up root"))
LOGK=ec.generate_private_key(ec.SECP256R1())
der=lambda c: c.public_bytes(serialization.Encoding.DER)
spki=lambda k: k.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
LOGID=hashlib.sha256(spki(LOGK)).digest()
TRUST_ROOT={"certificateAuthorities":[{"certChain":{"certificates":[{"rawBytes":base64.b64encode(der(INT)).decode()},{"rawBytes":base64.b64encode(der(ROOT)).decode()}]},
             "validFor":{"start":"2026-01-01T00:00:00Z"}}],
            "tlogs":[{"logId":{"keyId":base64.b64encode(LOGID).decode()},"publicKey":{"rawBytes":base64.b64encode(spki(LOGK)).decode(),"validFor":{"start":"2026-01-01T00:00:00Z"}}}]}
TRUST=sg.sigstore_trust(TRUST_ROOT)
def utf8(s): b=s.encode(); return bytes([0x0c,len(b)])+b
def leaf(key,uri,issuer="https://token.actions.githubusercontent.com",signer=None,signer_name=None,start=None,secs=600,eku=True):
    start=start or T0
    b=(x509.CertificateBuilder().subject_name(x509.Name([])).issuer_name(signer_name or INT.subject).public_key(key.public_key())
       .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(start+datetime.timedelta(seconds=secs))
       .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)]),critical=True)
       .add_extension(x509.UnrecognizedExtension(x509.ObjectIdentifier("1.3.6.1.4.1.57264.1.8"),utf8(issuer)),critical=False))
    if eku: b=b.add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CODE_SIGNING]),critical=False)
    return der(b.sign(signer or INTK,hashes.SHA384()))
def record(digest,repo=REPO,wf=WF,uri=None,issuer="https://token.actions.githubusercontent.com",signer=None,signer_name=None,
           start=None,secs=600,when=None,ptype="https://slsa.dev/provenance/v1",logk=None,sigk=None,eku=True,set_ok=True):
    key=ec.generate_private_key(ec.SECP256R1())
    st={"predicateType":ptype,"subject":[{"name":"x.whl","digest":{"sha256":digest}}],
        "predicate":{"buildDefinition":{"externalParameters":{"workflow":{"repository":f"https://github.com/{repo}","path":wf,"ref":"refs/heads/main"}}}}}
    payload=json.dumps(st).encode(); pt=b"application/vnd.in-toto+json"
    pae=b"DSSEv1 %d %s %d %s"%(len(pt),pt,len(payload),payload)
    sig=(sigk or key).sign(pae,ec.ECDSA(hashes.SHA256()))
    c=leaf(key,uri or f"https://github.com/{repo}/{wf}@refs/heads/main",issuer,signer,signer_name,start,secs,eku)
    pem=b"-----BEGIN CERTIFICATE-----\n"+base64.encodebytes(c)+b"-----END CERTIFICATE-----\n"
    body=base64.b64encode(json.dumps({"apiVersion":"0.0.1","kind":"dsse","spec":{"payloadHash":{"algorithm":"sha256","value":hashlib.sha256(payload).hexdigest()},
         "signatures":[{"signature":base64.b64encode(sig).decode(),"verifier":base64.b64encode(pem).decode()}]}}).encode()).decode()
    t=when or WHEN; lk=logk or LOGK
    msg=json.dumps({"body":body,"integratedTime":t,"logID":LOGID.hex(),"logIndex":7},sort_keys=True,separators=(",",":")).encode()
    setsig=lk.sign(msg if set_ok else msg+b"x",ec.ECDSA(hashes.SHA256()))
    entry={"logIndex":"7","logId":{"keyId":base64.b64encode(LOGID).decode()},"kindVersion":{"kind":"dsse","version":"0.0.1"},"integratedTime":str(t),
           "inclusionPromise":{"signedEntryTimestamp":base64.b64encode(setsig).decode()},"canonicalizedBody":body}
    return {"attestations":[{"bundle":{"dsseEnvelope":{"payload":base64.b64encode(payload).decode(),"payloadType":pt.decode(),"signatures":[{"sig":base64.b64encode(sig).decode()}]},
            "verificationMaterial":{"certificate":{"rawBytes":base64.b64encode(c).decode()},"tlogEntries":[entry]}}}]}
D=hashlib.sha256(b"made-up wheel").hexdigest()
A=lambda got,d=D,repo=REPO,trust=TRUST,more=None: sg.attestation_ok(got,d,repo,WF,trust=trust,more=more)
check(A(record(D)),"a good record passes")
check(A(record(D,uri=f"https://github.com/{REPO}/{WF}@refs/tags/v6.50.0")),"a release tag passes")
check(not A(record(D),d="0"*64),"a different file fails")
check(not A(record(D,repo="someone/else")),"another project's workflow fails")
check(not A(record(D,wf=".github/workflows/other.yml")),"another workflow fails")
check(not A(record(D,sigk=ec.generate_private_key(ec.SECP256R1()))),"signed with a different key fails")
check(not A(record(D,uri="https://github.com/someone/else/.github/workflows/release.yml@refs/heads/main")),"a certificate naming someone else fails")
check(not A(record(D,uri=f"https://github.com/{REPO}/{WF}@refs/heads/feature")),"another branch fails")
check(not A(record(D,uri=f"https://github.com/{REPO}/{WF}@refs/heads/main/x")),"only an exact name passes")
check(not A(record(D,issuer="https://accounts.example.test")),"a certificate for another sign-in service fails")
check(A(record(D,eku=False)),"a certificate without a usage list still passes (older ones had none)")
k=ec.generate_private_key(ec.SECP384R1())
check(not A(record(D,signer=k,signer_name=name("made-up intermediate"))),"a certificate not from the authority (same name, other key) fails")
check(not A(record(D,signer=ec.generate_private_key(ec.SECP384R1()),signer_name=name("anyone"))),"a self-made authority fails")
check(not A(record(D,start=T0-datetime.timedelta(hours=2))),"a certificate that had expired when the log recorded it fails")
check(not A(record(D,when=WHEN+3600)),"logged after the certificate expired fails")
check(not A(record(D,logk=ec.generate_private_key(ec.SECP256R1()))),"a log promise signed by the wrong key fails")
check(not A(record(D,set_ok=False)),"a broken log promise fails")
r=record(D); r["attestations"][0]["bundle"]["verificationMaterial"]["tlogEntries"]=[]
check(not A(r),"a record the public log never saw fails")
r=record(D); o=record(D)["attestations"][0]["bundle"]["verificationMaterial"]["tlogEntries"][0]
r["attestations"][0]["bundle"]["verificationMaterial"]["tlogEntries"]=[o]
check(not A(r),"a log entry for a different signing fails")
check(not A(record(D,ptype="https://in-toto.io/attestation/release/v0.2")),"a record that isn't build provenance doesn't count")
check(not A({"attestations":[]}) and not A({}) and not A(None),"no records: fails")
bad=record(D); bad["attestations"][0]["bundle"]["dsseEnvelope"]["payload"]="!!"
check(not A(bad),"garbage: fails, no crash")
bad=record(D); bad["attestations"][0]["bundle"]["verificationMaterial"]["certificate"]["rawBytes"]=base64.b64encode(b"\x30\x82\xff").decode()
check(not A(bad),"a broken certificate: fails, no crash")
# keys SpamGuard doesn't carry: it reads Sigstore's published list, and only that list can make it pass
asked=[]
check(not A(record(D),trust=sg.sigstore_trust({})),"made with keys not built in, no list: fails")
check(A(record(D),trust=sg.sigstore_trust({}),more=lambda: asked.append(1) or TRUST) and asked,"made with keys not built in: Sigstore's published list is read and accepted")
check(not A(record(D,signer=ec.generate_private_key(ec.SECP384R1()),signer_name=name("anyone")),more=lambda: TRUST),"a self-made authority still fails after reading the list")
check(not A(record(D),trust=sg.sigstore_trust({}),more=lambda: None),"Sigstore unreachable: fails")
# the published list is checked against Sigstore's own checksum
root=json.dumps(TRUST_ROOT).encode(); h=hashlib.sha256(root).hexdigest()
FUT="2099-01-01T00:00:00Z"
META={"timestamp.json":{"signed":{"expires":FUT,"meta":{"snapshot.json":{"version":5}}}},"5.snapshot.json":{"signed":{"meta":{"targets.json":{"version":3}}}},
      "3.targets.json":{"signed":{"targets":{"trusted_root.json":{"hashes":{"sha256":h}}}}}}
def get(u,body=root):
    p=u.split("sigstore.dev/",1)[1]
    if p.startswith("targets/"): check(p==f"targets/{h}.trusted_root.json","the list is fetched by its checksum"); return body
    return json.dumps(META[p]).encode()
check(sg.fetch_sigstore_root(get)["logs"].keys()==TRUST["logs"].keys(),"Sigstore's published list is read")
try: sg.fetch_sigstore_root(lambda u: get(u,root+b" ")); check(False,"a changed list is refused")
except ValueError: check(True,"a changed list is refused")
META["timestamp.json"]["signed"]["expires"]="2020-01-01T00:00:00Z"
try: sg.fetch_sigstore_root(get); check(False,"an expired list is refused")
except ValueError: check(True,"an expired list is refused")
# the real public record of SpamGuard 6.49.0 passes with the keys built in, and with nothing changed in it
real=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"attest-6.49.0.json")))
check(sg.attestation_ok(real,real["digest"],real["repo"],WF),"the real 6.49.0 record passes with Sigstore's built-in keys")
check(not sg.attestation_ok(real,"0"*64,real["repo"],WF),"the real record doesn't pass for another file")
import copy
noprom=copy.deepcopy(real)
for x in noprom["attestations"]:
    for t in x["bundle"]["verificationMaterial"]["tlogEntries"]: t.pop("inclusionPromise",None)
check(sg.attestation_ok(noprom,real["digest"],real["repo"],WF),"the real record also passes on the log's inclusion proof alone")
bp=copy.deepcopy(noprom)
for x in bp["attestations"]:
    for t in x["bundle"]["verificationMaterial"]["tlogEntries"]: t["inclusionProof"]["rootHash"]=base64.b64encode(b"\0"*32).decode()
check(not sg.attestation_ok(bp,real["digest"],real["repo"],WF),"a changed log proof fails")
# in the updater: a 404 stops the install, a good record lets it go on
g=guard(mock()); g._repo=lambda: REPO
real_ok=sg.attestation_ok; sg.attestation_ok=lambda got,d,repo,wf,trust=None,more=None: real_ok(got,d,repo,wf,trust=TRUST,more=more)
class R(io.BytesIO):
    def __enter__(s): return s
    def __exit__(s,*a): pass
def opener(resp):
    def f(req,timeout=0):
        if isinstance(resp,Exception): raise resp
        return R(json.dumps(resp).encode())
    return f
import urllib.request as ur
real=ur.urlopen
try:
    ur.urlopen=opener(urllib.error.HTTPError("u",404,"nf",{},None))
    try: g._check_build_attestation("x.whl",b"made-up wheel"); check(False,"404 stops it")
    except ValueError as e: check("no build record" in str(e),"404 stops it: %s"%e)
    ur.urlopen=opener(urllib.error.URLError("offline"))
    try: g._check_build_attestation("x.whl",b"made-up wheel"); check(False,"offline stops it")
    except ValueError as e: check("tried again later" in str(e),"offline: tried again later")
    ur.urlopen=opener(record(D))
    try: g._check_build_attestation("x.whl",b"made-up wheel"); check(True,"a good record lets it install")
    except ValueError as e: check(False,"good record refused: %s"%e)
    ur.urlopen=opener(record("1"*64))
    try: g._check_build_attestation("x.whl",b"made-up wheel"); check(False,"a mismatched record stops it")
    except ValueError as e: check("didn't check out" in str(e),"a mismatched record stops it")
finally:
    ur.urlopen=real; sg.attestation_ok=real_ok
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
