# openHop can send path hops as 1, 2 or 3 bytes each (path.hash.mode), and openHop's policy engine compares
# each hop as an exact string. So a route block must be written at the size openHop is sending now:
# a learnt 2-byte hop "2F1A" becomes "2F" when 1-byte hops are in use, and a 1-byte block can't match
# 2-byte hops, so it stays off (and is reported) until learnt again. All data made up.
import sys, logging, os
from harness import *
logging.disable(logging.WARNING)
from repeater.policy_engine import PolicyEngine
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
# 1. openHop's own engine: a rule compares each hop as an exact string
class P:
    def __init__(self, hops): self.hops = hops; self.payload = bytearray(b"\x00" * 8); self.transport_codes = [0, 0]
    def get_path_hashes_hex(self): return self.hops
    def get_payload_type(self): return 5
    def get_payload(self): return self.payload
def engine_hits(value, hops):
    rule = {"id": 1, "name": "t", "enabled": True, "then": {"action": "drop", "reason": "t"},
            "if": {"all": [{"field": "payload_type", "op": "equals", "value": 5},
                           {"field": "path_hashes", "op": "contains", "value": value}]}}
    eng = PolicyEngine({"enabled": True, "rules": [rule], "default_action": "allow"})
    return eng.evaluate(P(hops), {"payload_type": 5, "hop_count": len(hops)}).action == "drop"
check(engine_hits("2F", ["2F", "9C"]), "engine: 1-byte matches 1-byte")
check(engine_hits("2F1A", ["2F1A", "9C3B"]), "engine: 2-byte matches 2-byte")
check(not engine_hits("2F", ["2F1A", "9C3B"]), "engine: 1-byte does not match 2-byte")
# 2. SpamGuard writes its route rules at the current size
def route_values(g):
    main, tail = g.build_rule_sets()
    out = set()
    def walk(c):
        if isinstance(c, dict):
            if c.get("field") == "path_hashes" and c.get("op", "contains") == "contains":
                out.add(c.get("value"))
            for v in c.values(): walk(v)
        elif isinstance(c, list):
            for v in c: walk(v)
    for r in main + tail: walk(r.get("if", {}))
    return out
g = guard(mock())
def block(value):
    g.blocks.clear()
    g._add_block(f"hop:{value}", "hop", value, "test", "hop", ttl=3600)
g.hash_size = 1; block("2F1A")
check("2F" in route_values(g), f"1-byte openHop: 2-byte learnt hop written as its 1-byte form ({route_values(g)})")
check(g.hops_stale == 0, "1-byte openHop: nothing stale")
g.hash_size = 2; block("2F1A")
check("2F1A" in route_values(g), "2-byte openHop: 2-byte block written as is")
g.hash_size = 2; block("2F")
check("2F" not in route_values(g) and g.hops_stale >= 1, "2-byte openHop: 1-byte block left off and reported")
g.hash_size = 1; block("2F")
check("2F" in route_values(g), "1-byte openHop: 1-byte block still written")
# 3. the size is read from the newest routed packet
g.hash_size = 1
g._note_hash_size({"original_path": '["2F1A","9C3B"]'}); check(g.hash_size == 2, "size read from 2-byte path")
g._note_hash_size({"original_path": '["2F"]'}); check(g.hash_size == 1, "size read from 1-byte path")
g._note_hash_size({"original_path": "[]"}); check(g.hash_size == 1, "empty path leaves size alone")
check(g._same_hop("2F1A", "2F") and not g._same_hop("2F1A", "9C"), "hops match on the bytes both have")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
