# Every rule is checked before it goes to openHop. Shapes openHop could read as "match everything" (no conditions,
# nested groups) or that it doesn't understand are left out, reported once, and never sent; the good rules around
# them still go. Uses openHop's real rule engine where it is checked out. Made-up names and texts.
import os, sys, glob, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
P=sg.rule_problem
good={"id":1,"name":"t","enabled":True,"if":{"all":[{"field":"payload_type","op":"equals","value":5},{"field":"channel_sender","op":"equals","value":"Q Sender"}]},"then":{"action":"drop"}}
check(P(good) is None,"a sound rule passes")
def variant(**ch):
    import copy; r=copy.deepcopy(good)
    for k,v in ch.items(): r[k]=v
    return r
cases={
 "no conditions":variant(**{"if":{"all":[]}}),
 "a nested group":variant(**{"if":{"all":[{"any":[{"field":"payload_type","op":"equals","value":5}]}]}}),
 "an any-group at the top":variant(**{"if":{"any":[{"field":"payload_type","op":"equals","value":5}]}}),
 "a bare single condition":variant(**{"if":{"field":"channel_sender","op":"equals","value":"x"}}),
 "an unknown field":variant(**{"if":{"all":[{"field":"payload_hex","op":"equals","value":"00"}]}}),
 "an unknown operator":variant(**{"if":{"all":[{"field":"channel_sender","op":"regex","value":".*"}]}}),
 "an empty value":variant(**{"if":{"all":[{"field":"channel_sender","op":"in","value":[]}]}}),
 "an unknown action":variant(then={"action":"retire"}),
 "no id":variant(id=""),
 "a hold over a whole kind of packet":variant(**{"if":{"all":[{"field":"payload_type","op":"equals","value":5}]}}),
}
for what,r in cases.items(): check(P(r) is not None,"refused: "+what)
check(P(variant(**{"if":{"all":[{"field":"payload_type","op":"equals","value":5}]}},then={"action":"allow"})) is None,"an allow over a kind of packet is fine (it only lets things through)")
# openHop really does treat an empty list as matching everything: the reason for the check
try:
    sys.path.insert(0,glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),".openhop"))[0])
    from repeater.policy_engine import PolicyEngine
    pe=PolicyEngine.__new__(PolicyEngine)
    check(pe._rule_matches({"if":{"all":[]}},object(),{}) is True,"openHop matches every packet for an empty list (so it must never be sent)")
except Exception as ex:
    print("note: openHop's engine not available here:",type(ex).__name__)
# in place: a bad rule is left out, reported once, the others still go
m=mock(); g=guard(m, floodguard=True, spoof_watch=True)
g.apply_settings({"mode":"protect","machine_block":"all","public_bots":True,"drop_damaged":True})
for i in range(12): m.add(f"V{i}x",f"Buy now at q-shop.example {i}",["B1","A1","DE"],ago=600-i*20)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
main,tail=g.build_rule_sets()
n=len(main)+len(tail)
check(n>5 and not g.bad_rules,"every rule SpamGuard writes today passes (%d rules)"%n)
raw=g._build_rule_sets_raw
g._build_rule_sets_raw=lambda: (raw()[0]+[variant(id=999999,**{"if":{"all":[]}})], raw()[1])
main,tail=g.build_rule_sets(); main2,tail2=g.build_rule_sets()
check(len(main)+len(tail)==n and all(r.get("id")!=999999 for r in main),"the bad rule is left out, the rest still go")
check(sum("Left a rule out" in a["msg"] for a in g.activity)==1,"reported once in Activity, not on every sync")
check(g.bad_rules and "no conditions" in g.bad_rules[0][1],"and kept for Health")
g._build_rule_sets_raw=raw
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
