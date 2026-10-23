# The "N rules in openHop" line at the foot of the page opens a list of what each rule says, in plain English.
# Channel keys are never shown. All names and messages are made up.
import sys, logging, json
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
KEY="8b3387e9c5cdea6ac9e5edbaa115cd72"
r={"id":1,"name":"x","if":{"all":[{"field":"payload_type","op":"equals","value":5},{"field":"channel_hash","op":"equals","value":KEY},
   {"field":"channel_message_body","op":"contains","value":"buy cheap widgets now"},{"field":"channel_sender","op":"equals","value":"Spammy Sam"}]},"then":{"action":"drop"}}
t=sg.plain_rule(r)
check(t.startswith("Blocks a packet that is a channel message"),"starts with the action: "+t)
check("buy cheap widgets now" in t and "Spammy Sam" in t,"names the text and the sender: "+t)
check(KEY not in t and "8b33" not in t,"the channel key is never shown")
k={"id":2,"name":"known","if":{"all":[{"field":"payload_type","op":"equals","value":5},{"field":"channel_sender","op":"in","value":"@spamguard.known_senders"}]},"then":{"action":"allow"}}
check("someone SpamGuard knows" in sg.plain_rule(k) and sg.plain_rule(k).startswith("Lets through"),"known-people rule: "+sg.plain_rule(k))
f={"id":3,"name":"f","if":{"all":[{"field":"route_type","op":"equals","value":1},{"field":"hop_count","op":"gte","value":32},{"field":"local_transmission","op":"not_equals","value":True}]},"then":{"action":"log_only"}}
check("32 or more hops" in sg.plain_rule(f) and sg.plain_rule(f).startswith("Only watches"),"flood limit rule: "+sg.plain_rule(f))
check(sg.plain_rule({"if":{"all":[{"field":"mystery","op":"weird","value":"x"}]},"then":{"action":"drop"}}).endswith('mystery weird "x"'),"unknown conditions fall back to a plain form")
check(sg.plain_rule({"then":{"action":"drop"}})=="Blocks every packet","a rule with no conditions")
long=sg.plain_rule({"if":{"all":[{"field":"channel_message_body","op":"contains","value":"z"*300}]},"then":{"action":"drop"}})
check(len(long)<200,"long text is shortened")
# the status the page reads carries the description as a fourth item
m=mock(); g=guard(m, long_window_seconds=86400); g.apply_settings({"mode":"protect"})
T="Anyone using the fake-radio-shop dot example site should stop, it is run by somebody untrustworthy"
for i in range(5): m.add("Fenwick Fox",T,["4C","2F"],ago=9000-i*1500)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
rs=g.status()["rule_summary"]
check(rs["rules"] and all(len(x)==4 and isinstance(x[3],str) and x[3] for x in rs["rules"]),"every rule has a description: "+str(rs["rules"])[:160])
check(not any(KEY in x[3] for x in rs["rules"]) and not any(k for k in g.cfg["channels"].values() if any(k in x[3] for x in rs["rules"])),"no channel key in any description")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
