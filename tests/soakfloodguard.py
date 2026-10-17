# FloodGuard soak test: days of simulated mesh traffic, minute by minute, on a simulated clock, through
# FloodGuard's learning and openHop's own rule engine. Each scenario reports how much flood traffic this
# repeater stopped passing on, how much genuine traffic it held back, and what it learnt.
#   python3 tests/soakfloodguard.py            all scenarios (a few minutes)
#   python3 tests/soakfloodguard.py padded     one scenario
# Exits 1 if a scenario breaks its limits. All traffic is made up.
import sys, logging, math
from harness import *
logging.disable(logging.WARNING)

RADIO = {"spreading_factor": 8, "bandwidth": 62500, "coding_rate": 8, "preamble_length": 16}
DIRECT_TYPES = (2, 3)      # route types 2 and 3 are direct (routed)
CLOCK = [time.time()]
_real_time = time.time
time.time = lambda: CLOCK[0]


def poisson(lam):
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= random.random()
        if p <= L:
            return k
        k += 1


class Pkt:
    def __init__(s, route, ptype, hops):
        s.path = [os.urandom(1).hex().upper() for _ in range(hops)]
        s.payload = bytearray(os.urandom(40)); s.transport_codes = [0, 0]
        s.route, s.ptype = route, ptype
    def get_path_hashes_hex(s): return s.path
    def get_payload_type(s): return s.ptype
    def get_payload(s): return s.payload


def genuine(rate, far=False):
    """One minute of ordinary traffic: channel messages, direct messages and acks, adverts."""
    out = []
    for _ in range(poisson(rate)):
        r = random.random()
        if r < 0.40:
            route, ptype = 1, 5                       # channel message, flooded
        elif r < 0.75:
            route, ptype = random.choice([2, 2, 3]), random.choice([2, 3])   # direct message or ack
        elif r < 0.85:
            route, ptype = 1, 4                       # advert
        else:
            route, ptype = random.choice([0, 1]), 2   # path search / scoped flood
        hops = max(0, int(random.gauss(4, 1.6))) if not far else random.choice([2, 3, 4, 5, 6, 8, 10, 12])
        out.append(("g", route, ptype, min(hops, 14), random.randint(30, 90)))
    return out


def flood(rate, hops):
    return [("f", 1, 2, hops(), random.randint(45, 70)) for _ in range(poisson(rate))]


def run(name, days, minute, expect, flood_on=None):
    """minute(day, hour, m) -> list of packets for that minute. Returns a result dict."""
    m = mock()
    g = guard(m, mode="protect")
    g.radio = dict(RADIO); g.refresh_openhop_info = lambda *a, **k: None
    start = CLOCK[0] = _real_time() - days * 86400
    pe = None; rules_sig = None
    tally = {"f": 0, "f_stop": 0, "g": 0, "g_stop": 0, "d": 0, "d_stop": 0, "g_flood": 0, "g_flood_stop": 0}
    first_contain = {}
    for minute_no in range(int(days * 1440)):
        now = start + minute_no * 60
        CLOCK[0] = now
        day, hour = int(minute_no // 1440), int(minute_no % 1440 // 60)
        rules = g.build_rules()
        sig = json.dumps(rules, sort_keys=True)
        if sig != rules_sig:
            pe = PolicyEngine({"enabled": True, "default_action": "allow", "rules": rules,
                               "objects": {"spamguard": {"known_senders": g.known_list()}}})
            rules_sig = sig
        rows = []
        pk = minute(day, hour, minute_no % 60)
        for i, (kind, route, ptype, hops, length) in enumerate(pk):
            ts = now + i * 60.0 / max(1, len(pk))
            act = pe.evaluate(Pkt(route, ptype, hops), {"route_type": route, "payload_type": ptype, "hop_count": hops,
                                                         "local_transmission": False}).action
            drop = act == "drop"
            tally[kind] += 1; tally[kind + "_stop"] += drop
            if kind == "g" and route in DIRECT_TYPES:
                tally["d"] += 1; tally["d_stop"] += drop
            if kind == "g" and route in (0, 1):
                tally["g_flood"] += 1; tally["g_flood_stop"] += drop
            if kind == "f" and drop and day not in first_contain:
                first_contain[day] = ts
            rid = None
            if drop:
                rid = next((r["id"] for r in rules if r["then"]["action"] == "drop"
                            and "floodguard" in r["name"]), None)
            rows.append({"id": f"{minute_no}-{i}", "timestamp": ts, "type": ptype, "route": route, "length": length,
                         "rssi": -100, "snr": 2.0, "transmitted": not drop, "is_duplicate": False, "payload": "",
                         "packet_hash": os.urandom(8).hex(),
                         "original_path": json.dumps([os.urandom(1).hex().upper() for _ in range(hops)]),
                         **({"drop_reason": f"Policy blocked packet (rule {rid})"} if drop else {})})
        g.ingest(rows)
        g.fg_decide(now + 59)
    st = g.fg_status()
    pct = lambda a, b: round(100.0 * a / b, 1) if b else 0.0
    res = {"name": name, "flood_stopped": pct(tally["f_stop"], tally["f"]), "flood_pkts": tally["f"],
           "genuine_flood_held": pct(tally["g_flood_stop"], tally["g_flood"]),
           "genuine_held": pct(tally["g_stop"], tally["g"]), "direct_held": tally["d_stop"],
           "episodes": st["episodes"], "learnt": st["learnt"], "ready_day": round((g.fg.get("ready") or 0) - start) // 86400 if g.fg.get("ready") else None,
           "level": st["level"], "unscoped": g.cfg["flood_max_unscoped"], "advert": g.cfg["flood_max_advert"],
           "notes": [a["msg"] for a in list(g.activity)[:3]]}
    ok, why = True, []
    for k, (lo, hi) in expect.items():
        v = res[k]
        if v is None or v < lo or v > hi:
            ok = False; why.append(f"{k}={v} not in [{lo},{hi}]")
    res["ok"], res["why"] = ok, why
    return res


def padded_hops():   # Dutch-style flood: fabricated routes padded far beyond normal
    return random.randint(14, 60)


SCENARIOS = {
    # Quiet countryside: a few packets an hour, no floods. FloodGuard must do nothing at all.
    "quiet": (6, lambda d, h, m: genuine(0.4 if 7 <= h <= 22 else 0.1),
              {"genuine_held": (0, 0), "direct_held": (0, 0), "episodes": (0, 0)}),
    # Busy town mesh with an evening net: genuine bursts several times normal. No flood, so no harm.
    "busy": (6, lambda d, h, m: genuine(5 if 19 <= h <= 21 else 2.5 if 7 <= h <= 23 else 0.6),
             {"genuine_held": (0, 0.5), "direct_held": (0, 0)}),
    # Padded flood (as captured in the Netherlands): 25 packets a minute for 40 minutes each evening from day 4.
    "padded": (7, lambda d, h, m: genuine(2.5 if 7 <= h <= 23 else 0.6)
               + (flood(25, padded_hops) if d >= 4 and h == 20 and m < 40 else []),
               {"flood_stopped": (75, 100), "direct_held": (0, 0), "genuine_held": (0, 3), "episodes": (2, 6)}),
    # Short-path flood: no padding, starts 1-3 hops away. Hop limits can't tell it apart: shown honestly.
    "short": (7, lambda d, h, m: genuine(2.5 if 7 <= h <= 23 else 0.6)
              + (flood(25, lambda: random.randint(1, 3)) if d >= 4 and h == 20 and m < 40 else []),
              {"direct_held": (0, 0), "genuine_held": (0, 3)}),
    # On-off flood: five minutes on, five off, for two hours a night from day 4.
    "pulsed": (7, lambda d, h, m: genuine(2.5 if 7 <= h <= 23 else 0.6)
               + (flood(30, padded_hops) if d >= 4 and h in (20, 21) and (m // 5) % 2 == 0 else []),
               {"flood_stopped": (50, 100), "direct_held": (0, 0), "genuine_held": (0, 4)}),
    # Flood during the learning days (day 1 and 2): must not teach FloodGuard that long routes are normal,
    # and nothing is stopped while it is still learning.
    "learnflood": (6, lambda d, h, m: genuine(2.5 if 7 <= h <= 23 else 0.6)
                   + (flood(25, padded_hops) if d in (1, 2, 4) and h == 20 and m < 40 else []),
                   {"unscoped": (16, 20), "direct_held": (0, 0), "genuine_held": (0, 3), "flood_stopped": (10, 60)}),
    # Long-distance mesh: genuine routes up to 12 hops are normal here. Learnt limits must allow for that.
    "longhaul": (6, lambda d, h, m: genuine(2.0 if 7 <= h <= 23 else 0.5, far=True)
                 + (flood(25, padded_hops) if d >= 4 and h == 20 and m < 40 else []),
                 {"unscoped": (24, 32), "direct_held": (0, 0), "genuine_held": (0, 5), "flood_stopped": (50, 100)}),
    # A smaller flood (12 a minute) on the busy town mesh: harder to tell from a busy evening.
    "busyflood": (7, lambda d, h, m: genuine(5 if 19 <= h <= 21 else 2.5 if 7 <= h <= 23 else 0.6)
                  + (flood(12, padded_hops) if d >= 4 and h == 22 and m < 40 else []),
                  {"direct_held": (0, 0), "genuine_held": (0, 3)}),
    # Advert storm from far away: 10 adverts a minute from 10-20 hops for an hour a day from day 4.
    "adverts": (7, lambda d, h, m: genuine(2.5 if 7 <= h <= 23 else 0.6)
                + ([("f", 1, 4, random.randint(10, 20), 120) for _ in range(poisson(10))] if d >= 4 and h == 15 else []),
                {"flood_stopped": (90, 100), "direct_held": (0, 0), "genuine_held": (0, 1)}),
}

if __name__ == "__main__":
    random.seed(11)
    pick = [a for a in sys.argv[1:] if a in SCENARIOS] or list(SCENARIOS)
    bad = 0
    print(f"{'scenario':<11}{'flood stopped':>14}{'genuine held':>13}{'genuine flood held':>19}{'direct held':>12}{'floods':>7}  learnt (level / unscoped / adverts), day it started acting")
    for n in pick:
        days, minute, expect = SCENARIOS[n]
        r = run(n, days, minute, expect)
        bad += not r["ok"]
        print(f"{n:<11}{(str(r['flood_stopped'])+'%' if r['flood_pkts'] else '-'):>14}{str(r['genuine_held'])+'%':>13}{str(r['genuine_flood_held'])+'%':>19}{r['direct_held']:>12}{r['episodes']:>7}"
              f"  {r['level']}% / {r['unscoped']} / {r['advert']}, day {r['ready_day']}"
              + ("" if r["ok"] else "   FAIL: " + "; ".join(r["why"])), flush=True)
    print("ALL SCENARIOS WITHIN LIMITS" if not bad else f"{bad} SCENARIO(S) OUTSIDE LIMITS")
    sys.exit(1 if bad else 0)
