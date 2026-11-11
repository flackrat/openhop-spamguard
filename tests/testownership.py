# SpamGuard only touches its own rules in openHop, never switches the rule engine back on behind your back, and
# a damaged ownership marker can't lock it out. Made-up names and codes.
import sys, logging, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
m=mock(); g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"})
mine={"id":7,"name":"spamguard: my note - keep","enabled":True,"if":{"all":[{"field":"payload_type","op":"equals","value":99}]},"then":{"action":"drop"}}
m.policy["policy_engine"].setdefault("rules",[]).append(mine)
g._add_block("hop:AA","hop","AA","test","hop",ttl=3600); sync(g)
names=[r["name"] for r in m.policy["policy_engine"]["rules"]]
check("spamguard: my note - keep" in names,"a rule of yours with a similar name is kept")
check(any(n.startswith("spamguard:hop:AA") for n in names),"SpamGuard's own rule is written")
check(m.policy["policy_engine"].get("enabled") is True and g.engine_on_seen,"the rule engine is switched on the first time it is needed")
# You switch the rule engine off: it stays off, and Health says so
m.policy["policy_engine"]["enabled"]=False; sync(g); sync(g)
check(m.policy["policy_engine"]["enabled"] is False,"switched off by you: SpamGuard leaves it off")
h=g.health()
check(h["engine_off"] and any("rule engine is switched off" in p for p in h["problems"]),"Health says nothing is being blocked")
g.action("engine_on",{}); sync(g)
check(m.policy["policy_engine"]["enabled"] is True and not g.health()["engine_off"],"the button switches it back on")
# remembered across a restart
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.engine_on_seen,"remembered after a restart")
# A damaged or future-dated marker from 'another SpamGuard' never stops this one
for ts in ("yesterday", time.time()+10*365*86400, None, [1]):
    m.policy["policy_engine"].setdefault("objects",{})[sg.OWNER_KEY]={"id":"someone-else","ts":ts,"state":"active"}
    try: sync(g); okk=not getattr(g,"standby",None)
    except Exception as e: okk=False
    check(okk,f"marker time {str(ts)[:12]!r}: still in charge")
# removing SpamGuard's rules leaves yours
keep=[r for r in m.policy["policy_engine"]["rules"] if not sg.SpamGuard.is_our_rule(r)]
check("spamguard: my note - keep" in [r["name"] for r in keep] and not any(r["name"].startswith("spamguard:hop") for r in keep),"removal would leave your rule")
# A setting changed on the page stays across restarts, until you change it in the config file
m3=mock(); g3=guard(m3,floodguard=False,repeat_max=4)
g3.apply_settings({"repeat_max":7,"mode":"protect"}); g3._save_state(force=True)
g4=sg.SpamGuard(dict(g3.file_cfg))
check(g4.cfg["repeat_max"]==7 and g4.cfg["mode"]=="protect","page settings survive a restart with the file unchanged")
g5=sg.SpamGuard(dict(g3.file_cfg,repeat_max=5,mode="monitor"))
check(g5.cfg["repeat_max"]==5 and g5.cfg["mode"]=="monitor","a later change in the config file wins")
check(any("config file changed" in str(a) for a in g5.activity),"and Activity says so")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
