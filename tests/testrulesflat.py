# Every rule SpamGuard writes is one flat "all" list of plain field tests. Nested all/any groups can be
# mishandled by some openHop versions (matching every packet), so SpamGuard must never write them. All data made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def leaf(c):
    return isinstance(c, dict) and set(c) >= {"field", "op"} and "all" not in c and "any" not in c and "not" not in c

def flat(rule):
    cond=rule.get("if")
    if not (isinstance(cond, dict) and list(cond)==["all"] and isinstance(cond["all"], list) and cond["all"]):
        return False
    return all(leaf(c) for c in cond["all"])

m=mock(); g=guard(m, wardrive_block=True, signed_watch=True)
g.fg.update(ready=time.time(), limit=12, since=time.time(), last_step=time.time())
for i in range(3):
    g._add_block(f"text:{i}", "text", f"buy cheap mesh upgrades now number {i:03d}", "test", "campaign", ttl=3600)
g._add_block("words:1", "words", ["cheap", "upgrade"], "test", "campaign", ttl=3600)
g._add_block("hop:4C", "hop", "4C", "test", "hop", ttl=3600)
g._add_block("hop:4C2F", "hop", "4C2F", "test", "hop", ttl=3600)
g._add_block("route:4C>2F", "route", ["4C", "2F"], "test", "route", ttl=3600)
for i in range(3):
    g._add_block(f"suffix:{i}", "suffix", [f"{i:02X}", "2F"], "test", "rotation", ttl=3600)
    g.blocks[f"suffix:{i}"]["allow_ids"]={}
g._add_block("linkhost:example.test", "links", ["example.test/"], "test", "linkhost", ttl=3600)
g._add_block("links:new", "links", ["http"], "test", "links", ttl=3600)
g._add_block("lockdown", "lockdown", None, "test", "lockdown", ttl=3600)
main, tail = g.build_rule_sets()
rules=main+tail+g.build_rules()
check(len(rules)>10, f"a wide mix of rules was built: {len(rules)}")
bad=[r["name"] for r in rules if not flat(r)]
check(not bad, f"every rule is one flat list of plain tests; not flat: {bad[:5]}")
check(all(isinstance(r["if"]["all"], list) for r in rules if flat(r)), "and the lists are lists")

# the checker itself catches a nested group
check(not flat({"if":{"all":[{"field":"payload_type","op":"equals","value":5},{"any":[{"field":"hop_count","op":"equals","value":1}]}]}}),
      "the check rejects a nested any")
check(not flat({"if":{"all":[{"all":[{"field":"payload_type","op":"equals","value":5}]}]}}), "and a nested all")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
