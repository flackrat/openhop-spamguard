# The protection level slider and the advanced settings agree: every setting the slider moves is in all three
# presets and nothing else is, the default is the Balanced value, every level from 0 to 100 stays inside each
# setting's allowed range and moves one way only, and the settings that depend on each other never contradict
# each other at any level.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
M=sg.META_BY_KEY; P=sg.PRESETS; D=sg.DEFAULT_CONFIG
pk={m["key"] for m in sg.SETTINGS_META if m.get("preset")}
for name,p in P.items():
    check(set(p)==pk, f"{name}: the preset covers exactly the slider's settings {sorted(set(p)^pk)}")
for k in sorted(pk):
    check(D.get(k)==P["balanced"][k], f"{k}: the default is the Balanced value")
    vals=[sg.level_values(l)[k] for l in range(101)]
    lo,hi=M[k].get("min"),M[k].get("max")
    check(all((lo is None or v>=lo) and (hi is None or v<=hi) for v in vals), f"{k}: stays within {lo}-{hi} at every level")
    check(all(a<=b for a,b in zip(vals,vals[1:])) or all(a>=b for a,b in zip(vals,vals[1:])), f"{k}: moves one way only")
check(all(m["key"] in D for m in sg.SETTINGS_META), "every setting has a default")
for l in range(101):
    v={**D,**sg.level_values(l)}
    for name,cond in (("a burst limit above the repeat limit", v["repeat_max"]<v["name_budget_max"]),
                      ("a burst limit above a lively conversation (7 in ten minutes)", v["name_budget_max"]>=8),
                      ("slow repeats counted over at least as long as they are held", v["slow_repeat_window_seconds"]>=v["slow_repeat_hold_seconds"]),
                      ("new-name threshold at least the made-up-name one", v["hop_new_senders"]>=v["hop_random_senders"]),
                      ("two-hour threshold at least the ten-minute one", v["hop_random_senders_long"]>=v["hop_random_senders"]),
                      ("duplicates long enough to make a rule", v["dedupe_min_chars"]>=v["min_rule_chars"]),
                      ("repeat holds no longer than other blocks", v["repeat_block_seconds"]<=v["block_ttl_seconds"]),
                      ("route surge blocks no longer than other blocks", v["route_surge_ttl"]<=v["block_ttl_seconds"]),
                      ("duplicates looked for within the history kept", v["dedupe_seconds"]<=max(v["long_window_seconds"],v["dedupe_seconds"])),
                      ("a link campaign needs at least two names", v["link_campaign_names"]>=2)):
        if not cond: check(False, f"level {l}: {name}")
check(True,"no conflicts between settings at any level")
# the page gets the presets it needs to draw the slider
m=mock(); g=guard(m); st=g.status()
check(set(st["presets"]["balanced"])==pk, "the web page is given every setting the slider moves")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
