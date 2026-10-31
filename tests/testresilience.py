# Hard conditions: a restart, a state file damaged mid-write, openHop being unreachable and coming back, the
# rule limit at its ceiling, and messages whose signals disagree or are missing. Each must end somewhere safe:
# blocks kept, nobody genuine held, nothing crashing. All names, codes and texts are made up.
import sys, logging, time, os, json, urllib.error
from harness import *
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)

def spam_wave(m, n=8, path=("6A", "4D", "2F"), ago=300):
    for i in range(n):
        m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), list(path), ago=ago - i)

def settle(g):
    g.poll_once(); g.last_sync = 0; g.sync_pending = True; g.poll_once()

# a restart keeps what was learnt, and the rules written afterwards still do the same job
m = mock(); g = guard(m, known_min_msgs=3); g.apply_settings({"mode": "protect", "level": 50})
for i, t in enumerate(["Morning all", "Nice and clear", "Anyone about"]):
    m.add("Quarry Pete", t, ["4C", "2F"], ago=3000 - i * 60)
spam_wave(m)
settle(g)
spam_key = [k for k in g.blocks]
check(spam_key, "setup: the wave created blocks")
before = (m.decide(rname(), "FREE PRIZE claim now https://spam.example/x1", ["6A", "4D", "2F"]),
          m.decide("Quarry Pete", "Back again", ["4C", "2F"]))
g._save_state(force=True)
g2 = sg.SpamGuard(dict(g.file_cfg))
check(set(g2.blocks) == set(spam_key), "after a restart the blocks are all still there")
check(g2.is_known("Quarry Pete"), "and so are the people it knows")
g2.last_sync = 0; g2.sync_pending = True; g2.poll_once()
after = (m.decide(rname(), "FREE PRIZE claim now https://spam.example/x2", ["6A", "4D", "2F"]),
         m.decide("Quarry Pete", "Back again", ["4C", "2F"]))
check(before == after == ("drop", "allow"), f"the written rules still hold spam and let the regular through: {before} {after}")

# a state file damaged mid-write: the last good copy is used, and a leftover temp file is ignored
st = g.file_cfg["state_file"]
g._save_state(force=True); g._save_state(force=True)       # now there is a .bak
with open(st, "w") as f: f.write('{"blocks": {"x": ')       # cut off mid-write
with open(st + ".tmp", "w") as f: f.write("garbage")
g3 = sg.SpamGuard(dict(g.file_cfg))
check(set(g3.blocks) == set(spam_key), "a damaged state file falls back to the last good copy")
for p in (st, st + ".bak"):
    with open(p, "w") as f: f.write("not json")
g4 = sg.SpamGuard(dict(g.file_cfg))
check(g4.blocks == {}, "with both copies damaged it starts clean instead of crashing")

# openHop unreachable: nothing crashes, blocks stay, and it carries on when openHop returns
m = mock(); g = guard(m, known_min_msgs=3); g.apply_settings({"mode": "protect", "level": 50})
spam_wave(m); settle(g)
n_blocks = len(g.blocks)
real = g.cfg["openhop_url"]
g.cfg["openhop_url"] = "http://127.0.0.1:9"                  # nothing listens here
try:
    g.poll_once(); g.last_sync = 0; g.sync_pending = True; g.poll_once(); crashed = False
except urllib.error.URLError:
    crashed = False                  # the run loop expects this one, notes it and tries again
except Exception as e:
    crashed = repr(e)
check(not crashed, f"openHop being unreachable fails the way the run loop expects: {crashed}")
check(len(g.blocks) == n_blocks, "and no block is lost while it is away")
g.cfg["openhop_url"] = real
g.last_sync = 0; g.sync_pending = True; g.poll_once()
check(m.decide(rname(), "FREE PRIZE claim now https://spam.example/x3", ["6A", "4D", "2F"]) == "drop", "when it returns the rules are in place again")

# the rule limit has a ceiling that a settings change cannot raise
check(sg.META_BY_KEY["max_total_rules"]["max"] == 500, "the rule limit's ceiling is 500")
m = mock(); g = guard(m, max_total_rules=9999)
for i in range(700): g._add_block(f"text:{i}", "text", f"buy cheap mesh upgrades now number {i:04d}", "test", "campaign", ttl=3600)
main, tail = g.build_rule_sets()
check(len(main) + len(tail) <= 500, f"even a config file asking for more never writes more than 500 rules: {len(main) + len(tail)}")

# conflicting or missing signals
m = mock(); g = guard(m, known_min_msgs=3); g.apply_settings({"mode": "protect", "level": 50})
for i, t in enumerate(["Morning all", "Nice and clear", "Anyone about"]):
    m.add("Quarry Pete", t, ["4C", "2F"], ago=3000 - i * 60)
spam_wave(m, path=("6A", "4D", "2F"))
m.add("Zk3Q9T7W", "Does anyone know a good chip shop near the harbour?", ["3C", "2F"], ago=200)      # odd name, honest text, clean route
m.add("Quarry Pete", "Anyone seen the FREE PRIZE posts today? Reported them", ["6A", "4D", "2F"], ago=150)   # known name, spammy words, on a blocked route
m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), [], ago=100)               # no path at all (heard direct)
settle(g)
check(m.decide("Zk3Q9T7W", "Does anyone know a good chip shop near the harbour?", ["3C", "2F"]) == "allow", "an odd name with honest text on a clean route is not held")
check(m.decide("Quarry Pete", "Anyone seen the FREE PRIZE posts today? Reported them", ["6A", "4D", "2F"]) == "allow", "a known person is not held for quoting spam, even on a blocked route")
check(m.decide(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), ["6A", "4D", "2F"]) == "drop", "the spam itself is still held")
check(not any(b["kind"] == "hop" and b["value"] in ("3C", "4C") for b in g.blocks.values()), "no block lands on the clean routes")
st = g.status()
check(st and st["recent"], "the status still builds with a message that has no path")

print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
