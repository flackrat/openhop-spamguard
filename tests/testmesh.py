# How SpamGuard's rules sit with the user's own openHop rules, in openHop's real policy engine (through the
# harness, as the other tests do). Default order: SpamGuard's blocks, then the user's rules. With
# rules_after_yours on: the user's rules first. All data made up.
from harness import *
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
m = mock()
m.policy["policy_engine"]["rules"] += [
    {"id": 9001, "name": "user drop AB", "enabled": True, "then": {"action": "drop"},
     "if": {"all": [{"field": "payload_type", "op": "equals", "value": 5}, {"field": "path_hashes", "op": "contains", "value": "AB"}]}},
    {"id": 9002, "name": "user allow 2F", "enabled": True, "then": {"action": "allow"},
     "if": {"all": [{"field": "payload_type", "op": "equals", "value": 5}, {"field": "path_hashes", "op": "contains", "value": "2F"}]}}]
g = guard(m)
g._add_block("hop:2F", "hop", "2F", "test", "hop", ttl=3600)
g._add_block("text:spam", "text", "buy cheap mesh upgrades now", "test", "campaign", ttl=3600)
g.hash_size = 1
def sync():
    g.last_sync = 0; g.sync_pending = True; g.poll_once()
sync()
SPAM = "buy cheap mesh upgrades now"
check(m.decide("Alice", SPAM, ["9C"]) == "drop", "a text block drops its message")
check(m.decide("Alice", SPAM, ["2F"]) == "drop", "a text block beats a user's allow on the same route (before user rules)")
check(m.decide("Alice", "hello there friend", ["AB"]) == "drop", "the user's own drop rule still works")
check(m.decide("Alice", "hello there friend", ["9C"]) == "allow", "traffic nobody blocks goes through")
# Route blocks (the default kind) are written after the user's rules, so a user's allow for the route wins.
check(m.decide("Alice", "hello there friend", ["2F"]) == "allow", "GAP: by default a route block loses to a user's allow for the same route")
g.apply_settings({"rules_after_yours": True}); sync()
check(m.decide("Alice", "hello there friend", ["2F"]) == "allow", "with rules_after_yours on, the user's allow still wins")
check(m.decide("Alice", SPAM, ["2F"]) == "allow", "with the setting on, a user allow lets even a text block through (the setting's stated risk)")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
