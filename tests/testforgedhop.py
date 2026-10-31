# A spammer can put a trusted repeater's code at the front of a path to borrow its free pass through a route
# block. When made-up names from nobody established arrive wearing a trusted first hop, that code stops
# getting the pass on that route for a while. Ordinary people on the same first hop are not affected, and the
# pass comes back later. All names and codes are made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)

def setup():
    m = mock(); g = guard(m, known_min_msgs=3)
    g.apply_settings({"mode": "protect", "level": 50})
    now = time.time()
    g._add_block("suffix:t", "suffix", ["4D", "2F"], "test", "rotation", ttl=7200)
    g.blocks["suffix:t"]["allow_ids"] = {}
    g.routes["6A>4D>2F"] = [now - 900, now - 60, 5, 0]    # 6A has really sent normal traffic along 4D>2F
    g.routes["7E>4D>2F"] = [now - 900, now - 60, 4, 0]    # and so has 7E
    g.relays["6A"] = now
    g.relays["7E"] = now
    return m, g

m, g = setup()
b = g.blocks["suffix:t"]
check(g.allowed_origins(b) == {"6A", "7E"}, f"setup: both trusted first hops are allowed: {g.allowed_origins(b)}")

# a normal name on a trusted first hop changes nothing
m.add("Quarry Pete", "Morning all", ["6A", "4D", "2F"], ago=120)
g.poll_once()
check(g.allowed_origins(b) == {"6A", "7E"}, "a normal message on a trusted first hop changes nothing")

# made-up names wearing the trusted first hop 6A
for i in range(3):
    m.add(rname(), "FREE PRIZE claim now https://spam.example/" + rname(5), ["6A", "4D", "2F"], ago=100 - i)
g.poll_once()
ao = g.allowed_origins(b)
check("6A" not in ao, f"a trusted first hop that spam is wearing loses its pass on that route: {ao}")
check("7E" in ao, "other trusted first hops on the route keep theirs")
check(g.forged_hop("4D>2F", "6A", time.time()), "and it is remembered")

# on another route 6A is untouched
g.routes["6A>9C>2F"] = [time.time() - 900, time.time() - 60, 5, 0]
g._add_block("suffix:u", "suffix", ["9C", "2F"], "test", "rotation", ttl=7200)
g.blocks["suffix:u"]["allow_ids"] = {}
check("6A" in g.allowed_origins(g.blocks["suffix:u"]), "the same first hop keeps its pass on a different route")

# one odd device name on a trusted first hop is not enough
g2m, g2 = setup()
g2m.add("QX7R2MK9", "Hello there", ["7E", "4D", "2F"], ago=100)
g2m.add("QX7R2MK9", "Hello again", ["7E", "4D", "2F"], ago=50)
g2.poll_once()
check("7E" in g2.allowed_origins(g2.blocks["suffix:t"]), "a single odd name does not cost a trusted first hop its pass")

# the pass comes back after a while
g.forged[("4D>2F", "6A")] = {n: time.time() - g.FORGED_FOR - 60 for n in g.forged[("4D>2F", "6A")]}
check("6A" in g.allowed_origins(b), "the pass comes back once the spam has stopped")

# and the written rules follow: the forged first hop is no longer an exception
g.forged[("4D>2F", "6A")] = {n: time.time() for n in g.forged[("4D>2F", "6A")]}
g.last_sync = 0; g.sync_pending = True; g.poll_once()
check(m.decide(rname(), "FREE PRIZE claim now", ["6A", "4D", "2F"]) == "drop", "a spam message wearing 6A is held")
check(m.decide(rname(), "FREE PRIZE claim now", ["D2", "4D", "2F"]) == "drop", "and so is one from an unknown first hop")

print(f"{ok}/{ok+fail} passed")
sys.exit(1 if fail else 0)
