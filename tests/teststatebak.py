# Saved state survives a damaged file: each save keeps the previous good copy, and a damaged or empty state file
# is replaced by that copy on the next start, with a note saying so. Made-up names.
import sys, logging, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m)
g.known["Steady Sue"]=[time.time()-9*86400,time.time(),40]
g._save_state(force=True)
g.known["Steady Sue"][2]=41; g._save_state(force=True)
p=g.file_cfg["state_file"]
check(os.path.exists(p) and os.path.exists(p+".bak"), "each save keeps the previous copy")
for damage in (b"", b'{"blocks": {"x": ', b"\x00\x00\x00"):
    open(p,"wb").write(damage)
    g2=sg.SpamGuard(dict(g.file_cfg))
    check(g2.known.get("Steady Sue",[0,0,0])[2]>=40, f"a damaged state file ({damage[:12]!r}) is replaced by the last good copy")
    check(any("last good copy" in a["msg"] for a in g2.activity), "and Activity says so")
os.remove(p); os.remove(p+".bak")
g3=sg.SpamGuard(dict(g.file_cfg)); check(not g3.known.get("Steady Sue"), "with no saved state at all, it simply starts fresh")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
