# The release's software bill of materials: valid CycloneDX, lists the release and every pinned requirement.
import sys, os, json, re, tempfile, subprocess
root=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..")
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
out=os.path.join(tempfile.mkdtemp(),"sbom.json")
r=subprocess.run([sys.executable,os.path.join(root,"tools","make_sbom.py"),out],capture_output=True,text=True)
check(r.returncode==0,"make_sbom runs: "+r.stderr[-120:])
d=json.load(open(out))
check(d["bomFormat"]=="CycloneDX" and d["specVersion"],"CycloneDX header")
ver=re.search(r'^VERSION = "([0-9.]+)"',open(os.path.join(root,"spamguard.py")).read(),re.M).group(1)
check(d["metadata"]["component"]["version"]==ver,"the release version is in the file")
pins=re.findall(r'^([A-Za-z0-9_.-]+)==',open(os.path.join(root,"requirements.txt")).read(),re.M)
names={c["name"].lower() for c in d["components"]}
check(pins and all(p.lower() in names for p in pins),"every pinned requirement is listed")
check(all(c.get("hashes") for c in d["components"]),"each component carries its hashes")
rel=open(os.path.join(root,".github","workflows","release.yml")).read()
check("make_sbom.py" in rel and rel.count("sbom.cdx.json")>=4,"the release workflow builds, uploads and signs it")
dr=open(os.path.join(root,".github","workflows","dependency-review.yml")).read()
check("pull_request" in dr and "dependency-graph/compare" in dr,"dependency review runs on pull requests")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
