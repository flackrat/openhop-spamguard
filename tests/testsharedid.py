# Route blocks on a mesh that mixes hop sizes, and the shared-ID check. Each sender picks its own hop size,
# so one mesh carries 1-byte and 2-byte hops at once: route blocks are written at every size seen in the
# last day. A hop learnt at 2 bytes is only shortened to 1 byte when no other repeater heard in adverts
# shares that byte, because the short form would stop that repeater's traffic too. Every decision below
# goes through openHop's own policy engine. All keys and paths are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)

def sync(g):
    g.last_sync = 0; g.sync_pending = True; g.poll_once()

def advert(g, key_prefix, age=0.0, node_type=2):
    """A repeater advert with no location: a 32-byte key starting with key_prefix."""
    key = (key_prefix + "AB" * 32)[:64]
    payload = bytes.fromhex(key) + b"\0" * 68 + bytes([node_type])
    g.learn_advert({"payload": payload.hex(), "timestamp": time.time() - age, "original_path": "[]"})

def sizes(g, *hops_sizes):
    now = time.time()
    for n in hops_sizes:
        g._note_hash_size({"original_path": '["' + "2F1A9C"[: 2 * n] + '"]', "timestamp": now})

def hop_block(g, value, match=None):
    g.blocks.clear()
    g._add_block(f"hop:{value}", "hop", value, "test", "hop", ttl=3600, extra={"match": match} if match else None)

def drops(m, path):
    return m.decide(rname(), "hello there", path) == "drop"

# 1. A mixed mesh with no adverts heard: a 2-byte learnt hop is blocked at both sizes
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
sizes(g, 1, 2)
check(g.hop_sizes_in_use() == [1, 2], f"both sizes in use: {g.hop_sizes_in_use()}")
hop_block(g, "2F1A"); sync(g)
check(drops(m, ["2F", "9C"]), "1-byte hops through the blocked repeater are stopped")
check(drops(m, ["2F1A", "9C3B"]), "2-byte hops through the blocked repeater are stopped")
check(not drops(m, ["30", "9C"]), "other 1-byte routes still go out")
check(not drops(m, ["301A", "9C3B"]), "other 2-byte routes still go out")
check(g.hops_narrowed == 0 and g.hops_shared == 0 and g.hops_stale == 0, "nothing to report")
b = next(iter(g.blocks.values()))
ids = [r["id"] for r in m.policy["policy_engine"]["rules"]]
check(len(ids) == len(set(ids)), "every rule id is unique")
check(b["id"] in ids and set((b.get("size_ids") or {}).values()) <= set(ids), "block keeps its own id for one size")
check(set(g.rule_numbers(b)) >= {b["id"]} | set((b.get("size_ids") or {}).values()), "block lists both its rules")

# 2. Another repeater heard here shares the byte: the 1-byte form is left out, the 2-byte form stays
before = g.route_sig()
advert(g, "2F77")
check(g.route_sig() != before, "a new shared byte changes what rules depend on")
sync(g)
check(not drops(m, ["2F", "9C"]), "the other repeater's 1-byte traffic is no longer stopped")
check(drops(m, ["2F1A", "9C3B"]), "the blocked repeater is still stopped on 2-byte hops")
check(g.hops_narrowed == 1, f"reported as narrowed ({g.hops_narrowed})")
w = g.health().get("warnings", [])
check(any("not written in their shorter form" in x for x in w), f"Health explains it: {w}")

# 3. Hearing the blocked repeater itself doesn't count as a clash
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
sizes(g, 1, 2); advert(g, "2F1A"); hop_block(g, "2F1A"); sync(g)
check(drops(m, ["2F", "9C"]) and g.hops_narrowed == 0, "its own advert doesn't narrow the block")

# 4. A clash heard more than two weeks ago doesn't count
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
sizes(g, 1, 2); advert(g, "2F77", age=15 * 86400); hop_block(g, "2F1A"); sync(g)
check(drops(m, ["2F", "9C"]) and g.hops_narrowed == 0, "an old advert is ignored")

# 5. A 1-byte block on a byte two known repeaters use is kept and reported
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
sizes(g, 1); advert(g, "2F11"); advert(g, "2F22"); hop_block(g, "2F"); sync(g)
check(drops(m, ["2F", "9C"]), "the only form there is still applies")
check(g.hops_shared == 1, f"reported as shared ({g.hops_shared})")
check(any("more than one repeater" in x for x in g.health().get("warnings", [])), "Health warns about it")

# 6. A 1-byte block can't match 2-byte hops: left off on a 2-byte-only mesh and reported
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
g.hash_size = 2; sizes(g, 2); hop_block(g, "2F"); sync(g)
check(not drops(m, ["2F1A", "9C3B"]) and g.hops_stale == 1, "stale, as before")

# 7. A hop size not seen for over a day drops out
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
g.hop_sizes = {2: time.time() - 2 * 86400}; g.hash_size = 1
check(g.hop_sizes_in_use() == [1], f"old size dropped: {g.hop_sizes_in_use()}")

# 8. The default mode (known people let through) writes the same per-size rules after your own rules
m = mock(); g = guard(m, floodguard=False)
sizes(g, 1, 2); hop_block(g, "2F1A"); sync(g)
check(drops(m, ["2F", "9C"]) and drops(m, ["2F1A", "9C3B"]), "gated block covers both sizes")
advert(g, "2F77"); sync(g)
check(not drops(m, ["2F", "9C"]) and drops(m, ["2F1A", "9C3B"]), "gated block narrowed the same way")

# 9. Exact-path blocks
m = mock(); g = guard(m, floodguard=False, hop_match_mode="exact_paths")
sizes(g, 1, 2); hop_block(g, "2F1A", match="exact_paths")
b = next(iter(g.blocks.values())); b["paths"]["2F1A>9C3B"] = g._new_id(); sync(g)
check(drops(m, ["2F", "9C"]) and drops(m, ["2F1A", "9C3B"]), "exact path at both sizes")
check(not drops(m, ["2F", "30"]), "a different path still goes out")
advert(g, "9C55"); sync(g)
check(not drops(m, ["2F", "9C"]) and drops(m, ["2F1A", "9C3B"]), "a shared hop anywhere in the path narrows it")

# 10. Rule ids stay the same across rebuilds
m = mock(); g = guard(m, floodguard=False, hop_match_mode="contains")
sizes(g, 1, 2); hop_block(g, "2F1A"); sync(g)
first = sorted(r["id"] for r in m.policy["policy_engine"]["rules"])
sync(g); g.build_rule_sets(); sync(g)
check(sorted(r["id"] for r in m.policy["policy_engine"]["rules"]) == first, "ids stable")

# 11. Confidence for the map's pins: other repeaters heard here using the same code
m = mock(); g = guard(m, floodguard=False)
target = ("2F1A" + "CD" * 32)[:64]
check(g.code_share("2F", target) == {"others": 0, "unlocated": 0}, "no one else heard: sure")
advert(g, "2F77"); advert(g, "2F88")
cs = g.code_share("2F", target)
check(cs["others"] == 2 and cs["unlocated"] == 2, f"two others, neither on the map: {cs}")
check(g.code_share("2F1A", target)["others"] == 0, "the 2-byte code is still unique")
check(g.code_share("2F77", ("2F77" + "AB" * 32)[:64])["others"] == 0, "a repeater doesn't share with itself")
check(g.code_share("DIRECT") == {"others": 0, "unlocated": 0}, "direct messages have no code")
advert(g, "3A10", age=15 * 86400)
check(g.code_share("3A")["others"] == 0, "an advert older than two weeks doesn't count")

print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
