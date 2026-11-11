# Keeps working when something goes wrong: a failing check, a damaged state file, odd config values, a clock in
# the future, a flood of names, a full rule budget. All names and messages are made up.
import sys, logging, json, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()

# A check that fails does not stop the others: expiry, saving and syncing still happen, and health says so
m=mock(); g=guard(m)
g._add_block("hop:AA","hop","AA","test","hop",ttl=60)
g.blocks["hop:AA"]["expires"]=time.time()-1
real=g.decide
g.decide=lambda: (_ for _ in ()).throw(RuntimeError("detector broke"))
g.poll_once()
check("hop:AA" not in g.blocks,"expired blocks are still removed when detection fails")
h=g.health()
check(any("Spam detection hit an error" in p for p in h["problems"]),"health reports the failing check")
g.decide=real
fg=g.fg_decide; g.fg_decide=lambda: (_ for _ in ()).throw(ValueError("fg broke")); g.poll_once(); g.fg_decide=fg
check(any("FloodGuard hit an error" in w for w in g.health()["warnings"]),"a FloodGuard error is a warning, detection still runs")

# One packet stamped an hour ahead does not stop SpamGuard reading new ones
m2=mock(); g2=guard(m2); sync(g2)
m2.packets.append({"id":len(m2.packets)+1,"timestamp":time.time()+3600,"type":5,"payload":enc("Kim Lane","from the future"),
                   "packet_hash":"f"*16,"original_path":json.dumps(["A1"])})
sync(g2)
for i in range(3): m2.add("Lou Park",f"ordinary message {i}",["B2"])
sync(g2)
check(sum(1 for e in g2.events if e.sender=="Lou Park")==3,"new messages are still read after a future-stamped one")
check(g2.last_packet_ts<=time.time()+g2.CURSOR_AHEAD+1,"the reading point stays near now")
g2.last_packet_ts=time.time()+3600   # openHop's clock stepped back an hour after SpamGuard had read ahead
for i in range(2): m2.add("Max Dale",f"after the clock step {i}",["C3"])
sync(g2)
check(sum(1 for e in g2.events if e.sender=="Max Dale")==2,"after openHop's clock steps back, new messages are read")

# A state file of the right syntax but the wrong shape: start from the last good copy
m3=mock(); g3=guard(m3)
g3.known["Steady Sue"]=[time.time()-9*86400,time.time(),40]
g3._save_state(force=True); g3._save_state(force=True)
p=g3.file_cfg["state_file"]; good=json.load(open(p))
for name,mut in [("blocks as a list",{"blocks":["x"]}),("a history key that is text",{"hist":{"abc":1}}),
                 ("a rule id that is text",{"next_rule_id":"nine"})]:
    st=dict(good); st.update(mut); json.dump(st,open(p,"w"))
    try:
        g4=sg.SpamGuard(dict(g3.file_cfg)); started=True
    except Exception:
        started=False; g4=None
    check(started and g4.known.get("Steady Sue",[0,0,0])[2]>=40,f"{name}: starts, from the last good copy")

# Config values of the wrong type are read sensibly or ignored, never fatal
c=sg.coerce_config({"poll_seconds":"3","floodguard":"no","repeat_max":"lots","listen_api_key":123456,"allow_hops":"4C"})
check(c.get("poll_seconds")==3 and c.get("floodguard") is False,"numbers and yes/no written as text are read")
check("repeat_max" not in c,"an unreadable number is ignored (the default is used)")
check(c.get("listen_api_key")=="123456","an all-digit password stays a password")
check(c.get("allow_hops")==["4C"],"one repeater written without brackets becomes a list")

# A flood of made-up names can't grow the name history without limit
m5=mock(); g5=guard(m5)
now=time.time()
for i in range(g5.HISTORY_MAX+3000):
    g5.sender_history[f"n{i:06d}"]={"first":now-100+i*0.001,"count":1,"last":now-100+i*0.001,"hops":set()}
g5.ingest([])
check(len(g5.sender_history)<=g5.HISTORY_MAX,"name history stays within its cap")
check(f"n{g5.HISTORY_MAX+2999:06d}" in g5.sender_history,"and keeps the most recently heard names")

# A full rule budget never leaves out a lockdown you started
m6=mock(); g6=guard(m6,max_total_rules=20)
for i in range(30): g6._add_block(f"hop:{i:02X}","hop",f"{i:02X}","test","hop",ttl=3600)
g6.action("lockdown",{"minutes":15}); sync(g6)
names=[r["name"] for r in m6.policy["policy_engine"]["rules"]]
check(any("lockdown" in n for n in names),"lockdown rule written even with the budget full")
check(g6.stats.get("rules_left_out",0)>0,"and the blocks left out are counted")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
