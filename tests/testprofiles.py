# Settings profiles: save what's in force, apply one (only detection settings change), share as a file.
# A profile from a file is checked and never applied by itself; one holding channels, keys, the mode or
# unknown fields is refused. All values are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
g.apply_settings({"sensitivity":"strict"}); g.apply_settings({"repeat_max":5,"evidence_log":True})
g.action("profile_save",{"name":"Busy mesh"})
st=g.status()["profiles"]
p=st["list"][0]
check(p["name"]=="Busy mesh" and p["sensitivity"]=="strict" and p["values"]=={"repeat_max":5},"profile holds sensitivity and changed detection values only: "+str(p))
check(st["in_use"]=="Busy mesh" and not st["modified"],"in use, not modified")
g.apply_settings({"repeat_max":7})
check(g.status()["profiles"]["modified"],"a later change shows as modified")
g.apply_settings({"sensitivity":"relaxed"})
g.action("add_channel",{"name":"#trail"})
g.action("profile_apply",{"name":"Busy mesh"})
check(g.cfg["sensitivity"]=="strict" and g.cfg["repeat_max"]==5,"applying puts the values back")
check(g.cfg["mode"]=="protect" and "#trail" in g.cfg["channels"] and g.cfg.get("evidence_log"),"mode, channels and evidence log untouched")
# share as a file
exp={"format":"spamguard-profile","version":1,"name":"Dutch busy","sensitivity":"balanced","values":{"dedupe_min_chars":5}}
g.action("profile_import",{"profile":exp})
check(any(x["name"]=="Dutch busy" for x in g.status()["profiles"]["list"]),"imported")
check(g.cfg["repeat_max"]==5 and g.status()["profiles"]["in_use"]=="Busy mesh","importing never applies it")
for bad,why in [({"format":"spamguard-profile","version":1,"values":{"channels":{"x":"0"*32}}},"channels"),
                ({"format":"spamguard-profile","version":1,"mode":"protect"},"mode"),
                ({"format":"spamguard-profile","version":1,"values":{"evidence_log":False}},"evidence log"),
                ({"format":"spamguard-profile","version":1,"values":{"repeat_max":-4}},"out of range"),
                ({"format":"other","version":1},"other format")]:
    try: g.action("profile_import",{"profile":bad}); check(False,"refused: "+why)
    except ValueError: check(True,"")
g.action("profile_delete",{"name":"Dutch busy"})
check(not any(x["name"]=="Dutch busy" for x in g.status()["profiles"]["list"]),"deleted")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
