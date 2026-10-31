# A shared evidence file can have its repeater codes replaced as well as its names: the same code always
# becomes the same made-up code within one file, codes that start alike still start alike, nothing real is
# left in the routes or in block names, and every download is different. All names, codes and messages made up.
import sys, logging, time, json, os, re
from harness import *
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)

CODES = ["6A", "D8", "7E", "3C", "6AAB", "D8C2", "7E0145"]   # invented; two of them are longer forms of 6A and D8

m = mock(); g = guard(m, evidence_log=True, evidence_dir=os.path.join(TMP, "ev_rc"))
for i in range(4): m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), ["6A", "D8", "7E"], ago=300 - i)
for i in range(3): m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), ["6AAB", "D8C2", "7E0145"], ago=250 - i)
m.add("Hilltop Hiker", "Morning all, clear skies up here", ["3C", "2F"], ago=200)
g.poll_once(); g.last_sync = 0; g.sync_pending = True; g.poll_once()
g.action("block_hop", {"hop": "6A"})
g.note("Repeater 6A: something happened on route 6A>D8 and 3C")
g.poll_once(); g.log_messages(list(g.events)); g.evidence.flush(force=True)

def rows(text): return [json.loads(l) for l in text.splitlines() if l.strip()]
def paths(rs): return [r["path"] for r in rs if r.get("type") == "msg"]

plain = rows(g.evidence.export(1, False))
check(any(p == ["6A", "D8", "7E"] for p in paths(plain)), "setup: real routes are in the unscrambled file")

names_only = g.evidence.export(1, True)                     # the old behaviour: names scrambled, routes untouched
check(any(p == ["6A", "D8", "7E"] for p in paths(rows(names_only))), "routes=False leaves the codes alone")

a = rows(g.evidence.export(1, True, True))
b = rows(g.evidence.export(1, True, True))
pa = paths(a)
check(len(pa) == len(paths(plain)) and pa, "same number of messages")
check(all(len(x) == len(y) and all(len(i) == len(j) for i, j in zip(x, y)) for x, y in zip(paths(plain), pa)),
      "routes keep their length and each code keeps its width")

# a bijection: the same code always maps to the same new code, and different codes stay different
mp = {}
consistent = True
for x, y in zip(paths(plain), pa):
    for i, j in zip(x, y):
        if mp.setdefault(i, j) != j: consistent = False
check(consistent, "the same code always becomes the same made-up code")
check(len(set(mp.values())) == len(mp), "different codes stay different")

# codes that start alike still start alike
check(mp["6AAB"][:2] == mp["6A"] and mp["D8C2"][:2] == mp["D8"] and mp["7E0145"][:2] == mp["7E"], "longer forms of a repeater keep their start")
check(mp["6AAB"] != mp["6A"], "but are still a different code")

# no real code is left where codes live. A made-up code can by chance equal a real one, so look at which
# fields still hold a code that maps to something different.
def codes_in(v):
    if isinstance(v, str): return re.findall(r"(?<![0-9A-Za-z])(?:6AAB|D8C2|7E0145|6A|D8|7E|3C)(?![0-9A-Za-z])", v)
    if isinstance(v, list): return [c for x in v for c in codes_in(x)]
    if isinstance(v, dict): return [c for x in v.values() for c in codes_in(x)]
    return []
left = [c for r in a if r.get("type") in ("msg", "block", "note") for k in ("path", "caught_by", "key", "value", "msg", "reason")
        for c in codes_in(r.get(k)) if mp.get(c, c) != c and c not in mp.values()]
check(not left, "no real code is left in routes, block names or notes: " + str(left[:5]))
blk = [r for r in a if r.get("type") == "block"]
caught = {r["caught_by"] for r in a if r.get("type") == "msg" and r.get("caught_by")}
check(blk and all(r["key"] != "hop:6A" for r in blk), "block names are scrambled")
check(all(c == "hop:" + mp["6A"] for c in caught if c.startswith("hop:")), "caught_by names match the scrambled routes")
note = [r["msg"] for r in a if r.get("type") == "note" and "something happened" in r.get("msg", "")]
check(note and mp["6A"] in note[0] and "6A>" not in note[0], "notes that mention a code are covered: " + str(note))

# names are still scrambled, message text is still kept, and every download is different
check(all(r["sender"].startswith("N-") for r in a if r.get("type") == "msg"), "names are scrambled as before")
check(any("FREE PRIZE" in r.get("text", "") for r in a if r.get("type") == "msg"), "message text is kept")
check(pa != paths(b), "each download uses a different mapping")

# real routes from a plain export must not appear in a scrambled one unless the code happened to map to itself
leak = [p for p in pa if p in ([x for x in paths(plain)])]
check(len(leak) <= 1, "a scrambled route doesn't equal a real one (barring chance)")

# a replay of a scrambled-routes file still runs
import replay
p = os.path.join(TMP, "rc.jsonl")
open(p, "w", encoding="utf-8").write(g.evidence.export(1, True, True))
msgs, labels, settings = replay.load(p)
check(len(msgs) == len(pa) and all(m["sender"].startswith("N-") for m in msgs), "replay can read the scrambled file")
check(len({tuple(m["path"]) for m in msgs}) == len({tuple(x) for x in paths(plain)}), "and sees the same number of distinct routes")

print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
