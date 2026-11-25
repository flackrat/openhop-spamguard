# Running unattended: a failed save keeps the change waiting and is tried again (and Health says so), a start
# from the backup copy shows on Health, background jobs that keep failing show on Health, and the page never
# waits forever for a first picture. Made-up data only.
import sys, os, time, json, threading, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g=guard(mock())
path=g.cfg["state_file"]
g._save_state(force=True); first=g._last_save
check(os.path.exists(path),"a save works")
# make saving fail: a folder where the temporary file should go
real_open=os.open
def broken(p,*a,**k):
    if str(p).endswith(".tmp"): raise OSError(28,"No space left on device")
    return real_open(p,*a,**k)
os.open=broken
try:
    g._important=True; g._last_save=0; g._save_state(force=True)
    check(g._important,"a failed save keeps the change waiting to be saved")
    check(g._last_save==0,"a failed save isn't counted as a save")
    h=g.health(); check(any("couldn't save its data" in w for w in h["warnings"]) and h["save_failures"]==1,"Health says saving failed")
    g._save_state(force=True); check(g._save_failures==1,"not retried on every check (waits a little)")
    g._save_state(force=True, final=True); check(g._save_failures==2,"a final save on stopping always tries")
finally:
    os.open=real_open
g._save_failed_at=0; g._save_state(force=True)
check(not g._important and g._last_save>0 and not g._save_failures,"once saving works again, it saves and the warning goes")
check(not any("couldn't save" in w for w in g.health()["warnings"]),"warning gone")
# starting from the backup copy
open(path,"w").write("{damaged")
g2=sg.SpamGuard(dict(g.file_cfg, state_file=path))
check(getattr(g2,"_restored_from_backup",False),"a damaged file: carried on from the backup")
check(any("last good copy" in w for w in g2.health()["warnings"]),"Health says it started from the backup")
# background jobs that keep failing
def bad(): raise RuntimeError("made-up failure")
bad.__name__="refresh_neighbours"
g.refresh_neighbours=bad
for i in range(6): g.poll_once()
g.task_fails["refresh_neighbours"]["since"]-=600
check(any("reading the neighbour list" in w for w in g.health()["warnings"]),"a background job failing for a while shows on Health")
g.refresh_neighbours=lambda: None; g.refresh_neighbours.__name__="refresh_neighbours"
g.poll_once()
check(not any("neighbour list" in w for w in g.health()["warnings"]),"and goes once it works again")
# the page never waits forever for a first picture
g3=guard(mock()); g3.STATUS_START_WAIT=0.3
if hasattr(g3,"_last_status"): del g3._last_status
held=threading.Event(); done=threading.Event()
def hold():
    with g3.lock:
        held.set(); done.wait(5)
threading.Thread(target=hold,daemon=True).start(); held.wait(2)
t=time.time(); out=g3.status_now(wait=0.2); done.set(); time.sleep(0.1)
check(out is None and time.time()-t<2,"busy before the first picture: says it is starting instead of waiting")
check(isinstance(g3.status_now(),dict),"and answers normally once free")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
