# The updater checks GitHub's build record before installing: a provenance naming the file's sha256, made by this
# project's release workflow, signed with the certificate it carries. A missing, changed, wrongly signed or
# other-project record means the file isn't installed. Records here are made up, signed with a throwaway key.
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
def cert(key,uri):
    n=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"test")]); t=datetime.datetime(2026,1,1)
    c=(x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(key.public_key()).serial_number(1)
       .not_valid_before(t).not_valid_after(t+datetime.timedelta(days=1))
       .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)]),critical=False).sign(key,hashes.SHA256()))
    return c.public_bytes(serialization.Encoding.DER)
def record(digest,repo=REPO,wf=WF,signer=None,certkey=None,uri=None,ptype="https://slsa.dev/provenance/v1"):
    key=certkey or ec.generate_private_key(ec.SECP256R1())
    st={"predicateType":ptype,"subject":[{"name":"x.whl","digest":{"sha256":digest}}],
        "predicate":{"buildDefinition":{"externalParameters":{"workflow":{"repository":f"https://github.com/{repo}","path":wf,"ref":"refs/heads/main"}}}}}
    payload=json.dumps(st).encode(); pt=b"application/vnd.in-toto+json"
    pae=b"DSSEv1 %d %s %d %s"%(len(pt),pt,len(payload),payload)
    sig=(signer or key).sign(pae,ec.ECDSA(hashes.SHA256()))
    der=cert(key,uri or f"https://github.com/{repo}/{wf}@refs/heads/main")
    return {"attestations":[{"bundle":{"dsseEnvelope":{"payload":base64.b64encode(payload).decode(),"payloadType":pt.decode(),"signatures":[{"sig":base64.b64encode(sig).decode()}]},
            "verificationMaterial":{"certificate":{"rawBytes":base64.b64encode(der).decode()}}}}]}
D=hashlib.sha256(b"made-up wheel").hexdigest()
A=lambda got,d=D,repo=REPO: sg.attestation_ok(got,d,repo,WF)
check(A(record(D)),"a good record passes")
check(not A(record(D),d="0"*64),"a different file fails")
check(not A(record(D,repo="someone/else")),"another project's workflow fails")
check(not A(record(D,wf=".github/workflows/other.yml")),"another workflow fails")
check(not A(record(D,signer=ec.generate_private_key(ec.SECP256R1()))),"signed with a different key fails")
check(not A(record(D,uri="https://github.com/someone/else/.github/workflows/release.yml@refs/heads/main")),"a certificate naming someone else fails")
check(not A(record(D,ptype="https://in-toto.io/attestation/release/v0.2")),"a record that isn't build provenance doesn't count")
check(not A({"attestations":[]}) and not A({}) and not A(None),"no records: fails")
bad=record(D); bad["attestations"][0]["bundle"]["dsseEnvelope"]["payload"]="!!"
check(not A(bad),"garbage: fails, no crash")
# in the updater: a 404 stops the install, a good record lets it go on
g=guard(mock()); g._repo=lambda: REPO
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
    ur.urlopen=real
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
