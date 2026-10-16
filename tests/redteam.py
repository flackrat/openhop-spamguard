# Red-team simulation: a long, mixed spam attack against SpamGuard and openHop's real rule engine.
# A simulated clock runs about four hours (one hour of normal chat to learn the regulars, then three hours
# of overlapping attacks of many kinds) while genuine people keep chatting. Every message is judged by
# openHop's policy engine with the rules SpamGuard had written at the moment it arrived, so "stopped"
# means the repeater would really not have passed it on. Not part of the normal test run (slow):
#   python3 tests/redteam.py            (prints a report; exit code 0)
# All names, messages and repeaters are made up.
import sys, os, json, time as _time, random, string, logging, statistics, resource, collections
from harness import *
logging.disable(logging.WARNING)
random.seed(int(os.environ.get("SEED", "7")))

CLOCK = [_time.time()]
_time.time = lambda: CLOCK[0]          # one simulated clock for SpamGuard, the mock openHop and the packets

CH = {"Public": sg.PUBLIC_CHANNEL_KEY, "#chat": sg.hashtag_secret("#chat"), "#test": sg.hashtag_secret("#test")}
m = mock()
g = guard(m, hashtag_channels=["#chat", "#test"], known_min_msgs=3)
g.apply_settings({"mode": "monitor"})   # like a real install: watch first, then Protect

def hexhop(): return "%04X" % random.randrange(0x1000, 0xFFFF)
LOCAL = ["2F0E", "2F0E"]                # the last hop before us is our neighbour
GOOD_ENTRIES = ["A71C", "B30F", "C4D2", "D5E6", "E19A"]   # C4D2 is also used by an attacker (collateral)

def add_raw(text_with_sender, path, key):
    """A packet whose plaintext is exactly this (lets us send messages without a 'Name: ' prefix)."""
    k = sg._secret32(key)
    pt = int(CLOCK[0]).to_bytes(4, "little") + b"\x00" + text_with_sender.encode("utf-8", "surrogatepass")
    pt += b"\x00" * ((-len(pt)) % 16)
    from Crypto.Cipher import AES as _A
    import hmac as _h, hashlib as _hl
    ct = _A.new(k[:16], _A.MODE_ECB).encrypt(pt)
    m.packets.append({"id": len(m.packets) + 1, "timestamp": CLOCK[0], "type": 5,
                      "payload": (bytes([sg.channel_hash_byte(key)]) + _h.new(k, ct, _hl.sha256).digest()[:2] + ct).hex(),
                      "packet_hash": os.urandom(8).hex(), "original_path": json.dumps(path)})

def decide_raw(text_with_sender, path, key):
    from repeater.policy_engine import PolicyEngine
    k = sg._secret32(key)
    pt = int(CLOCK[0]).to_bytes(4, "little") + b"\x00" + text_with_sender.encode("utf-8", "surrogatepass")
    pt += b"\x00" * ((-len(pt)) % 16)
    from Crypto.Cipher import AES as _A
    import hmac as _h, hashlib as _hl
    ct = _A.new(k[:16], _A.MODE_ECB).encrypt(pt)
    payload = bytes([sg.channel_hash_byte(key)]) + _h.new(k, ct, _hl.sha256).digest()[:2] + ct
    class P:
        def __init__(s): s.payload = bytearray(payload); s.transport_codes = [0, 0]
        def get_path_hashes_hex(s): return path
        def get_payload_type(s): return 5
        def get_payload(s): return s.payload
    d = PolicyEngine(m.policy["policy_engine"]).evaluate(P(), {"payload_type": 5, "hop_count": len(path)})
    LAST_RULE[0] = next((r.get("name") for r in m.policy["policy_engine"]["rules"] if r.get("id") == d.rule_id), None)
    return d.action
LAST_RULE = [None]
RULE_HITS = collections.Counter()

STATS = collections.defaultdict(lambda: {"sent": 0, "passed": 0, "first_stop": None, "start": None, "examples": []})
GENUINE = collections.defaultdict(lambda: {"sent": 0, "dropped": 0, "examples": []})

def send(kind, sender, text, path, channel="Public", nameless=False):
    key = CH[channel]
    raw = text if nameless else f"{sender}: {text}"
    verdict = decide_raw(raw, path, key)
    add_raw(raw, path, key)
    if kind.startswith("genuine"):
        s = GENUINE[kind]; s["sent"] += 1
        if verdict == "drop":
            s["dropped"] += 1
            RULE_HITS[(kind, LAST_RULE[0], int((CLOCK[0]-start)/60) if 'start' in globals() else -1)] += 1
            if len(s["examples"]) < 4: s["examples"].append(f"{sender}: {text[:50]} via {'>'.join(path)}")
    else:
        s = STATS[kind]; s["sent"] += 1
        if s["start"] is None: s["start"] = CLOCK[0]
        if verdict != "drop":
            s["passed"] += 1
            if len(s["examples"]) < 3: s["examples"].append(f"{sender}: {text[:60]!r} via {'>'.join(path) or 'direct'}")
        elif s["first_stop"] is None: s["first_stop"] = CLOCK[0]

# ---------- people ----------
FIRST = ["Peter", "Lotte", "Sanne", "Daan", "Bram", "Femke", "Joris", "Anouk", "Ruben", "Iris", "Thijs", "Eva",
         "Koen", "Lisa", "Stijn", "Noor", "Jasper", "Fleur", "Wouter", "Sophie", "Gijs", "Mila"]
REGULARS = [f"{n} {random.choice('ABCDEFGHJKLMNPRSTVW')}" for n in FIRST] + \
           ["Hilltop Hiker", "Canal Boat Ted", "Base Camp 3", "PD3XYZ", "PA0QRS", "M0ABC", "NL-ALM-P2W", "NL-HRN-TST",
            "Radio Ruth", "Quarry Pete"]
REG_ENTRY = {r: random.choice(GOOD_ENTRIES) for r in REGULARS}
CHAT = ["Goedemorgen allemaal", "Anyone hearing me from the dyke?", "Nice signal today", "Radio check please",
        "Copy that, loud and clear", "Heading out for a walk, 73", "Is the repeater on the church back up?",
        "Weer een mooie dag", "Thanks for the relay!", "Testing my new antenna", "Who's on tonight?",
        "Lekker weertje", "Signal report 5/9 here", "Back home now", "Good evening mesh"]
TOPICS = ["the weather", "my new antenna", "the repeater on the church", "tonight's net", "the dyke road", "battery life",
          "the solar panel", "range to Utrecht", "the firmware update", "my Heltec", "the club meeting", "the hike"]
def chat_line():
    # mostly individual sentences, sometimes a stock greeting that many people use
    if random.random() < 0.25:
        return random.choice(["Goedemorgen allemaal", "Good evening mesh", "Radio check please", "73 all"]) + random.choice(["", "!", " :)"])
    return random.choice(["Anyone tried ", "Question about ", "Update on ", "Thinking about ", "Nice day for "]) + random.choice(TOPICS) + \
        random.choice(["?", ".", "!", " today", " this week"]) + random.choice(["", "", " " + str(random.randint(1, 99))])

def genuine_tick():
    for r in REGULARS:
        if random.random() < 1 / 90:          # roughly one message per regular per 15 simulated minutes
            send("genuine-regular", r, chat_line(), [REG_ENTRY[r]] + LOCAL[:1], random.choice(["Public"] * 4 + ["#chat"]))

newcomers = []
def newcomer_tick(t_attack):
    # new people keep arriving during the attacks, some through the repeater the attacker also uses
    if random.random() < 1 / 120:
        n = random.choice(["Henk", "Marloes", "Bas", "Tim", "Ilse", "Rik", "Joost", "Vera"]) + " " + random.choice("BDGKMRSTVW")
        newcomers.append(n)
        send("genuine-newcomer", n, random.choice(["Hoi, ik ben nieuw hier", "First time on the mesh, hello!",
                                                    "Can anyone hear me?", "Hallo allemaal"]),
             [random.choice(GOOD_ENTRIES)] + LOCAL[:1])

# ---------- attacks ----------
def rnd(n=8): return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))
def tagged(): return random.choice(FIRST) + random.choice(["", str(random.randint(1, 999))]) + random.choice("-_.") + \
    "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(5))
GARB = "ĔІブꝁャŸづ␧Чᵐᦐ৺иŉ☰Ĭя☆ッםᴋǴш░┛ᵀᵃ▸ภœ϶ʋ⚙ɾ⁂⊂♬Ï┤╫☙ɛԅ☼ᚦ∰ʬ⌖ꙮ☍ᛃ"
def garbage(n): return "".join(random.choice(GARB) for _ in range(n))
HOMO = str.maketrans({"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "i": "і", "x": "х"})
def variant(base):
    t = base
    r = random.random()
    if r < 0.2: t = t.translate(HOMO)                                   # look-alike letters
    elif r < 0.4: t = "​".join(t[i:i + 3] for i in range(0, len(t), 3))   # zero-width spaces
    elif r < 0.6: t = t.replace(" ", random.choice(["  ", " . ", " ✨ ", "_"]))
    elif r < 0.8: t = "".join(c.upper() if random.random() < 0.5 else c for c in t)
    return t + random.choice(["", " 🔥", " !!!", f" #{random.randint(10, 99)}"])
ZALGO = "̶̧̣̀́̂̃̈̊"
def zalgo(s): return "".join(c + "".join(random.choice(ZALGO) for _ in range(random.randint(1, 4))) for c in s)

ATTACKS = []   # (name, start_min, end_min, every_seconds, fn)
def attack(name, start, end, every):
    def deco(fn): ATTACKS.append((name, start, end, every, fn)); return fn
    return deco

@attack("1 random-name campaign, one entry repeater", 0, 20, 20)
def a1(): send("1 random-name campaign, one entry repeater", rnd(), "FREE PRIZE claim now https://spam.example/" + rnd(5), ["C4D2", "9E01"] + LOCAL[:1])

@attack("2 entry repeater changes every message", 25, 55, 20)
def a2(): send("2 entry repeater changes every message", rnd(), "Crypto signals, join the group t.me/" + rnd(6).lower(), [hexhop(), "9E01"] + LOCAL[:1])

@attack("3 first names with random tags, short garbage", 40, 60, 15)
def a3(): send("3 first names with random tags, short garbage", tagged(), garbage(random.randint(3, 12)), ["7A11", hexhop()] + LOCAL[:1])

@attack("4 same text disguised, plain human names", 60, 90, 25)
def a4(): send("4 same text disguised, plain human names", random.choice(FIRST) + random.choice(["", " " + random.choice("ABCDEFG")]),
               variant("win free bitcoin now visit coin-bonus example"), [random.choice(["5B5B", "6C6C", "7D7D"]), "9E01"] + LOCAL[:1])

@attack("5 copies known regulars' names", 95, 115, 30)
def a5(): send("5 copies known regulars' names", random.choice(REGULARS), "Join my channel for free gifts: gift-box.example/" + rnd(4), ["F00D", "9E01"] + LOCAL[:1])

@attack("6 slow drip, once every 6 minutes", 0, 180, 360)
def a6(): send("6 slow drip, once every 6 minutes", rnd(), "Cheap LoRa modules wholesale, message me", [hexhop(), "9E01"] + LOCAL[:1])

@attack("7 same spam on several channels", 120, 140, 20)
def a7(): send("7 same spam on several channels", rnd(), "Make 500 euro a day from home, ask me how", ["8E8E", "9E01"] + LOCAL[:1], random.choice(list(CH)))

@attack("8 no repeaters on the route (direct)", 140, 155, 20)
def a8(): send("8 no repeaters on the route (direct)", rnd(), "Visit lucky-spin.example for your bonus " + rnd(3), [])

@attack("9 unicode tricks: zalgo, RTL, emoji names", 150, 170, 20)
def a9():
    kind = random.random()
    name = rnd() if kind < 0.4 else ("".join(random.choice("🔥💰🎁🚀💎🍀") for _ in range(3)) if kind < 0.7 else "‮" + rnd(6))
    send("9 unicode tricks: zalgo, RTL, emoji names", name, zalgo("free gift card here") if random.random() < 0.6 else "\U00050000\U00060001 ok",
         ["9F9F", hexhop()] + LOCAL[:1])

@attack("10 links with different domains", 160, 180, 25)
def a10(): send("10 links with different domains", rnd(), "Hello all, check this out " + random.choice(["bit.ly", "t.ly", "tinyurl.com", "rb.gy"]) + "/" + rnd(6).lower(),
                [random.choice(["ABAB", "BCBC"]), "9E01"] + LOCAL[:1])

@attack("11 long word salad", 100, 125, 30)
def a11(): send("11 long word salad", rnd(), " ".join(random.choice(["mesh", "radio", "signal", "free", "now", "click", "best", "deal", "today", "lora", "node", "win"]) for _ in range(22)),
                ["CDCD", hexhop()] + LOCAL[:1])

@attack("12 no name in front", 125, 140, 30)
def a12(): send("12 no name in front", "", "SPAM SPAM buy followers cheap " + rnd(4), ["DEDE", "9E01"] + LOCAL[:1], nameless=True)

@attack("13 burst flood, several a second", 170, 173, 0.4)
def a13(): send("13 burst flood, several a second", rnd(), random.choice(["FLOOD", "SPAMWAVE", "XXXX"]) + " " + rnd(12), [hexhop(), hexhop()] + LOCAL[:1])

@attack("14 genuine phrases wrapped round spam", 75, 100, 25)
def a14(): send("14 genuine phrases wrapped round spam", rnd(), random.choice(CHAT) + " " + random.choice(["see promo-deal.example", "free gift at promo-deal.example"]) + " " + rnd(3),
                ["EFEF", "9E01"] + LOCAL[:1])

# ---------- run ----------
TICK = 10
poll_times, rule_peak = [], 0
def tick(step_s=TICK, attacks_on=True, t_min=0.0):
    global rule_peak
    genuine_tick()
    if attacks_on:
        newcomer_tick(t_min)
        for name, s, e, every, fn in ATTACKS:
            if s <= t_min < e:
                n = step_s / every
                k = int(n) + (1 if random.random() < n - int(n) else 0)
                for _ in range(k): fn()
    t0 = _time.perf_counter(); g.poll_once(); poll_times.append(_time.perf_counter() - t0)
    rule_peak = max(rule_peak, len([r for r in m.policy["policy_engine"]["rules"] if str(r.get("name", "")).startswith("spamguard:")]))
    CLOCK[0] += step_s

# six hours of ordinary chat in Monitor first, then Protect (as the automatic switch would)
for _ in range(2160): tick(attacks_on=False)
WARM = {"known": len(g.known_list()), "blocks": len(g.blocks)}
g.apply_settings({"mode": "protect"})
# special genuine events during the attack window
events = {30: "net", 85: "alert", 130: "net"}
start = CLOCK[0]
wall0 = _time.perf_counter()
for i in range(int(180 * 60 / TICK)):
    t_min = (CLOCK[0] - start) / 60
    ev = events.get(int(t_min))
    if ev and abs(t_min - int(t_min)) < 1e-6:
        if ev == "net":   # weekly net: many regulars answer with the same few words
            for r in random.sample(REGULARS, 12): send("genuine-net check-in", r, "Checking in for the net, 73", [REG_ENTRY[r]] + LOCAL[:1])
        else:             # a few people forward the same road alert
            for r in random.sample(REGULARS, 4): send("genuine-forwarded alert", r, "Road closed at the N201 roundabout after an accident, avoid", [REG_ENTRY[r]] + LOCAL[:1])
    tick(t_min=t_min)
    # the burst attack runs in sub-ticks
    if 170 <= t_min < 173:
        for _ in range(4): tick(step_s=2, t_min=t_min)
wall = _time.perf_counter() - wall0

# ---------- report ----------
print("\nSpamGuard red-team simulation (6 h of normal chat in Monitor, then 3 h of attacks in Protect, judged by openHop's rule engine)")
print(f"After the warm-up: {WARM['known']} of {len(REGULARS)} regulars known, {WARM['blocks']} blocks\n")
tot_s = tot_p = 0
for name, *_ in ATTACKS:
    s = STATS[name]; tot_s += s["sent"]; tot_p += s["passed"]
    rate = 100 * (s["sent"] - s["passed"]) / max(s["sent"], 1)
    first = "-" if s["first_stop"] is None else f"{(s['first_stop'] - s['start']) / 60:.1f} min"
    print(f"{name:48} sent {s['sent']:4}  stopped {rate:5.1f}%  first stop after {first}")
    for ex in s["examples"][:2]: print(f"{'':52}got through: {ex}")
print(f"\n{'ALL SPAM':48} sent {tot_s:4}  stopped {100 * (tot_s - tot_p) / max(tot_s, 1):5.1f}%")
print()
for k, s in GENUINE.items():
    print(f"{k:48} sent {s['sent']:4}  wrongly stopped {s['dropped']:3} ({100 * s['dropped'] / max(s['sent'], 1):.1f}%)")
    for ex in s["examples"][:3]: print(f"{'':52}{ex}")
print(f"\nMost SpamGuard rules in openHop at once: {rule_peak} (limit {g.cfg['max_total_rules']})")
print(f"SpamGuard check time per poll: median {statistics.median(poll_times) * 1000:.0f} ms, 95th percentile "
      f"{sorted(poll_times)[int(len(poll_times) * .95)] * 1000:.0f} ms, worst {max(poll_times) * 1000:.0f} ms over {len(poll_times)} polls")
print(f"Memory (peak resident): {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB; wall time {wall:.0f} s")
print(f"Known people at the end: {len(g.known_list())}; blocks at the end: {len(g.blocks)}")

print("\nRules that stopped genuine messages (kind, rule, minute):")
for k, v in RULE_HITS.most_common(15): print(" ", v, k)
print("\nBlocks at the end:", collections.Counter((b["kind"], b.get("source")) for b in g.blocks.values()))
print([ (k, b.get("value"), b.get("source")) for k,b in g.blocks.items() if b["kind"] in ("hop","suffix","lockdown","links")][:20])

# ---------- pass / fail (used by run_all.sh) ----------
spam_rate = 100 * (tot_s - tot_p) / max(tot_s, 1)
reg = GENUINE["genuine-regular"]; reg_fp = 100 * reg["dropped"] / max(reg["sent"], 1)
okk = spam_rate >= 90 and reg_fp <= 3 and GENUINE["genuine-net check-in"]["dropped"] == 0 and rule_peak <= g.cfg["max_total_rules"]
print(f"\n{'PASS' if okk else 'FAIL'}: {spam_rate:.1f}% of spam stopped (need 90), {reg_fp:.1f}% of regulars' messages wrongly stopped (need 3 or less)")
print(f"{1 if okk else 0} passed, {0 if okk else 1} failed")
sys.exit(0 if okk else 1)
