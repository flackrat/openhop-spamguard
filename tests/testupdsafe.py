# The root updater never writes through links planted in SpamGuard's own state folder, and keeps its own
# working files (install log, copy of the current version) in a folder only root can write. Made-up paths.
import os, sys, json, subprocess, tempfile, stat
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
# The long-running service is confined: these settings must stay in its unit file
unit=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","openhop-spamguard.service")).read()
for d in ("NoNewPrivileges=yes","ProtectSystem=full","PrivateTmp=yes","UMask=0077","RestrictAddressFamilies=","User=repeater"):
    check(d in unit,"the service file keeps "+d)
if os.geteuid()!=0:
    print("(skipping the rest: the updater runs as root)"); print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
HERE=os.path.dirname(os.path.abspath(__file__))
T=tempfile.mkdtemp(prefix="sgupd-")
STATE=os.path.join(T,"state"); ROOT=os.path.join(T,"rootstate"); os.makedirs(STATE)
victim=os.path.join(T,"victim.txt"); open(victim,"w").write("untouched\n")
os.symlink(victim,os.path.join(STATE,"update-status.json.tmp"))
open(os.path.join(STATE,"update-request"),"w").write(json.dumps({"version":"not-a-version"}))
env=dict(os.environ,SG_CONF=os.path.join(T,"none.yaml"),SG_APP=os.path.join(T,"app"),SG_STATE=STATE,SG_ROOT_STATE=ROOT)
r=subprocess.run(["bash",os.path.join(HERE,"..","update.sh"),"--from-request"],env=env,capture_output=True,text=True,timeout=60)
check(open(victim).read()=="untouched\n","a link planted as the status file's temporary copy is not written through")
st=os.path.join(STATE,"update-status.json")
check(os.path.isfile(st) and not os.path.islink(st) and json.load(open(st))["state"]=="failed","the status is still written, as a plain file")
check(os.stat(victim).st_uid==0,"the linked file's owner is unchanged")
check(os.path.isdir(ROOT) and not (os.stat(ROOT).st_mode & (stat.S_IWGRP|stat.S_IWOTH)),"root's working folder is writable by root only")
check(not os.path.exists(os.path.join(STATE,"update-install.log")) and not os.path.exists(os.path.join(STATE,"previous-version")),
      "no install log or copy of the current version in SpamGuard's own folder")
# Root touches SpamGuard's own folder only for the status file and the request it reads, never for its own files
src=open(os.path.join(HERE,"..","update.sh")).read()
uses=[l.strip() for l in src.splitlines() if "$STATE" in l and not l.strip().startswith("#")]
allowed=("STATUS=$STATE/","REQUEST=$STATE/","install -d -o repeater -g repeater \"$STATE\"","STATE=${SG_STATE")
check(all(any(a in l for a in allowed) for l in uses),"root writes nothing else in SpamGuard's own folder: "+"; ".join(l for l in uses if not any(a in l for a in allowed)))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
