# A route code shared by several repeaters heard here can't say which of them the spam came through. The status
# says how sure each code is (confirmed, probable or ambiguous), and one sign alone does not block everything
# with an ambiguous short code: it needs a second. All names, codes and keys are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)

def setup(keys, signals):
    m = mock(); g = guard(m)
    g.apply_settings({"mode": "protect", "level": 50})
    now = time.time()
    for k in keys: g.node_ids[k] = now
    for i in range(8): m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), ["6A", "4D", "2F"], ago=300 - i)
    g.hop_signals = lambda h: list(signals)
    g.poll_once(); g.last_sync = 0; g.sync_pending = True; g.poll_once()
    return m, g

A = "6A" + "11" * 15 + "01"
B = "6A" + "22" * 15 + "02"
C = "7E" + "33" * 15 + "03"
m, g = setup([A, B, C], [])
check(g.code_confidence("6A") == "ambiguous", "two repeaters heard with the same code: ambiguous")
check(g.code_confidence("7E") == "confirmed", "one repeater heard with the code: confirmed")
check(g.code_confidence("D8") == "probable", "none heard: probable, from routes alone")

# one sign on an ambiguous code: held back, with a note
m, g = setup([A, B], ["8 made-up names"])
check("hop:6A" not in g.blocks, "one sign on a code two repeaters share does not block everything with it")
check(any("Held back from blocking code 6A" in str(n) for n in g.activity), "and it says why")
# the same sign on a confirmed code blocks as before
m, g = setup([A], ["8 made-up names"])
check("hop:6A" in g.blocks, "one sign on a confirmed code blocks as before")
m, g = setup([], ["8 made-up names"])
check("hop:6A" in g.blocks, "one sign on a code nobody has been heard with blocks as before")
# two signs on an ambiguous code block
m, g = setup([A, B], ["8 made-up names", "a campaign through it"])
check("hop:6A" in g.blocks, "two independent signs on an ambiguous code block")
# longer codes are not held back: they are far less likely to be shared
m = mock(); g = guard(m); g.apply_settings({"mode": "protect", "level": 50})
for k in ("6AAB" + "11" * 14, "6AAB" + "22" * 14): g.node_ids[k] = time.time()
check(g.code_confidence("6AAB") == "ambiguous", "a longer code shared by two is still labelled ambiguous")

st = g.status()
m, g = setup([A, B], [])
check(any(h["hop"] == "6A" and h.get("confidence") == "ambiguous" for h in g.status()["hops"]), "the status shows each code's confidence")
print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
