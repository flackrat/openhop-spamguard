# openHop can send path hops as 1, 2 or 3 bytes each (path.hash.mode). SpamGuard's hop and suffix rules
# match the hop values it learned, and openHop's policy engine compares each hop as an exact string.
# So a block learned as "2F" (1-byte) should not match a 2-byte hop "2F1A". This checks that with the
# real openHop policy engine, and that a block learned at the same size still matches. All data made up.
import sys, logging, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".openhop")); sys.path.insert(0, os.path.join(HERE, ".openhop_core", "src"))
from repeater.policy_engine import PolicyEngine
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
class P:
    def __init__(self, hops): self.hops = hops; self.payload = bytearray(b"\x00" * 8); self.transport_codes = [0, 0]
    def get_path_hashes_hex(self): return self.hops
    def get_payload_type(self): return 5
    def get_payload(self): return self.payload
def rule(value):
    # the shape SpamGuard writes for a hop block: payload type, the hop present, and the hop count
    return {"id": 1, "name": "spamguard:test", "enabled": True,
            "if": {"all": [{"field": "payload_type", "op": "equals", "value": 5},
                           {"field": "path_hashes", "op": "contains", "value": value}]},
            "then": {"action": "drop", "reason": "test"}}
def hits(value, hops):
    eng = PolicyEngine({"enabled": True, "rules": [rule(value)], "default_action": "allow"})
    return eng.evaluate(P(hops), {"payload_type": 5, "hop_count": len(hops)}).action == "drop"
check(hits("2F", ["2F", "9C"]), "1-byte block matches 1-byte path")
check(hits("2F1A", ["2F1A", "9C3B"]), "2-byte block matches 2-byte path")
check(not hits("2F", ["2F1A", "9C3B"]), "EXPECTED GAP: a 1-byte block misses a 2-byte path")
check(not hits("2F1A", ["2F", "9C"]), "a 2-byte block misses a 1-byte path")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
