# Sparing the SD card: state is saved compressed, routine saves at most every 15 minutes, urgent saves noticed by
# the checking loop at most every 30 seconds, and the plain file an older version wrote is left alone so a rolled
# back update still starts with its data. Whichever copy was saved last is the one loaded. Made-up data only.
import sys, os, time, json, gzip, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock()
for i in range(30): m.add(f"Quarry Walker {i}",f"Morning all from the ridge, number {i}",["A7","2F"],ago=3000-i*60)
g=guard(m); g.poll_once()
base=g.cfg["state_file"]
# an older version's plain file is there from before the update
old=dict(read_state(base) if os.path.exists(base+".gz") else g.state_dict(), version="6.50.0")
old["allow_hops"]=["7Q"]
json.dump(old,open(base,"w")); os.utime(base,(time.time()-600,time.time()-600))
g._save_state(force=True)
check(os.path.exists(base+".gz") and open(base+".gz","rb").read(2)==b"\x1f\x8b","saved compressed")
check(json.load(open(base))["version"]=="6.50.0","the older version's plain file is left as it was")
raw,packed=g.state_bytes
check(packed*3<raw,f"compressed to well under a third ({packed} of {raw} bytes)")
check(read_state(base)["version"]==sg.VERSION,"the compressed copy is read first when it is newer")
g2=sg.SpamGuard(dict(g.file_cfg)); check("7Q" not in g2.allow_hops,"a restart loads the newer compressed copy")
# rolled back, the older version saves its plain file; updating again loads that, as it is newer
old["allow_hops"]=["8Q"]; json.dump(old,open(base,"w"))
os.utime(base+".gz",(time.time()-60,time.time()-60))
g3=sg.SpamGuard(dict(g.file_cfg)); check("8Q" in g3.allow_hops,"after a rollback, the newer plain file wins")
# how often
check(g.SAVE_EVERY==900 and g.SAVE_URGENT_GAP==30,"routine every 15 minutes, urgent at most every 30 seconds")
g._last_save=time.time()-100; t0=g._last_save; g._save_state(); check(g._last_save==t0,"no routine save within 15 minutes")
g._last_save=time.time()-901; g._save_state(); check(g._last_save>t0,"a routine save after 15 minutes")
g._important=True; g._last_save=time.time()-5; t1=g._last_save; g.poll_once()
check(g._last_save==t1 and g._important,"an urgent change noticed 5 s after a save waits (kept for the next save)")
g._last_save=time.time()-31; g.poll_once()
check(not g._important,"and is saved once 30 seconds have passed")
g._last_save=time.time()-1; t2=g._last_save; g.action("dismiss_link",{"id":"0123456789"})
check(g._last_save>t2,"a change you make on the page is saved at once")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
