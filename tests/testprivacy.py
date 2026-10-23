# The privacy check (tools/privacy_check.py) finds personal details and private blocklist entries in files,
# added lines and commit messages, never prints what it found, and passes the repository as it is.
# Everything here is made up.
import os, subprocess, sys, tempfile, shutil
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL=os.path.join(REPO,"tools","privacy_check.py")
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def run(args,cwd,env=None):
    e=dict(os.environ); e.pop("GITHUB_ACTIONS",None); e.pop("PRIVACY_BLOCKLIST",None); e.update(env or {})
    r=subprocess.run([sys.executable,TOOL,*args],cwd=cwd,capture_output=True,text=True,env=e)
    return r.returncode, r.stdout+r.stderr

# 1. The repository itself is clean
rc,out=run(["--tree"],REPO)
check(rc==0,"the repository passes: "+out[-300:])

# 2. A scratch repository with planted details
d=tempfile.mkdtemp()
def git(*a): subprocess.run(["git",*a],cwd=d,check=True,capture_output=True)
git("init","-q"); git("config","user.email","t@example.com"); git("config","user.name","t")
open(os.path.join(d,"a.txt"),"w").write("nothing personal here\n"); git("add","."); git("commit","-qm","start")
git("branch","base")
planted={"email":"write to someone.real@mailbox.co.uk","coords":"home is at 52.123,-1.456 roughly",
         "postcode":"post it to ZE9 9ZZ please","ip":"the pi is on 192.168.7.42","locator":"grid square IO91wm",
         "secret":"meet at Quillborough green"}
open(os.path.join(d,"b.txt"),"w").write("\n".join(planted.values())+"\n")
git("add","."); git("commit","-qm","add notes about Quillborough")
BL={"PRIVACY_BLOCKLIST":"# my private words\nquillborough\nre:\\bIO91\\w\\w\\b\n"}
rc,out=run(["--tree"],d,BL)
check(rc==1,"findings make it fail")
for k in ("email address","map coordinates","UK postcode","home network address","private blocklist entry #1","private blocklist entry #2"):
    check(k in out,f"finds {k}: {out}")
check(not any(v.split()[-2] in out or v.split()[-1] in out for v in planted.values()),"never prints what it found: "+out)
check("Quillborough" not in out and "quillborough" not in out,"never prints blocklist entries")
rc,out=run(["--diff","base"],d,BL)
check(rc==1 and "commit " in out and "message line" in out,"checks commit messages too: "+out)
check("b.txt:" in out,"and the added lines: "+out)
# 3. The allow file lets made-up values through
open(os.path.join(d,".privacy-allow"),"w").write("52.123,-1.456\n")
rc,out=run(["--tree"],d)
check("map coordinates" not in out,"an allowed made-up value is let through: "+out)
# 4. No-reply and example addresses are fine
open(os.path.join(d,"c.txt"),"w").write("noreply@anthropic.com 123+abc@users.noreply.github.com you@example.com\n")
git("add","."); git("commit","-qm","c")
rc,out=run(["--diff","HEAD~1"],d)
check(rc==0,"no-reply and example addresses pass: "+out)
# 5. Pull request text
rc,out=run(["--text-env","T"],d,{"T":"Fixes the map near 52.555,-1.444","PRIVACY_BLOCKLIST":""})
check(rc==1 and "T line 1: map coordinates" in out,"checks pull request text: "+out)
shutil.rmtree(d)

# 6. The Presidio helper: only the readable parts of code are looked at, and it never fails a run
sys.path.insert(0,os.path.join(REPO,"tools"))
import presidio_check as pc
check(pc.readable_parts("x.py",'m.add("Rowan Hill",TEXT)  # a made-up name')==["Rowan Hill"," a made-up name"],"code: quoted text and comments only")
check(pc.readable_parts("x.html","const a={b:1};let c=`${d}`;")==[],"script lines in pages are skipped")
check(pc.readable_parts("x.md","Meet at the <b>green</b>")==["Meet at the  green "],"documents: the whole line, without tags")
r=subprocess.run([sys.executable,os.path.join(REPO,"tools","presidio_check.py"),"--staged"],cwd=REPO,capture_output=True,text=True)
check(r.returncode==0,"it never fails, installed or not: "+r.stdout[-200:]+r.stderr[-200:])
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
