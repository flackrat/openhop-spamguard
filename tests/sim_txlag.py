# Simulation of the delay between sending a message and it going out, using openHop's real scheduling
# code (RepeaterHandler.schedule_retransmit and _calculate_tx_delay, with the airtime model from airtime.py),
# and a modelled radio. The radio's listen-before-talk (busy chance, backoff, attempts) and the traffic
# level are assumptions, not measurements, so read the numbers as shape and scale, not as your radio's
# exact figures. Time is scaled down (K) so many messages run quickly; reported times are scaled back up.
import asyncio, os, random, statistics, sys, types, logging
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '.openhop')); sys.path.insert(0, os.path.join(HERE, '.openhop_core', 'src'))
from unittest import mock
for name in ["paho", "paho.mqtt", "paho.mqtt.client"]:
    sys.modules.setdefault(name, mock.MagicMock())
logging.disable(logging.CRITICAL)
import repeater.engine as E
from repeater.airtime import AirtimeManager

K = 0.05                                   # real seconds per simulated second
REAL_SLEEP = asyncio.sleep
async def sim_sleep(d, *a, **k):
    await REAL_SLEEP(max(0.0, d) * K)
asyncio.sleep = sim_sleep                   # every wait in the engine runs on the scaled clock

RADIO = {"frequency": 869618000, "bandwidth": 62500, "spreading_factor": 8, "coding_rate": 8, "preamble_length": 16}
PKT_LEN = 110                               # a typical text message, bytes
LBT_ATTEMPTS = 5                            # openHop's default lbt_max_attempts

class Pkt:
    def __init__(self, flood=True): self.flood = flood; self.header = 0
    def get_raw_length(self): return PKT_LEN
    def is_route_flood(self): return self.flood
    def is_route_direct(self): return not self.flood
    def get_path_hashes_hex(self): return []

class Modem:
    """A radio that listens before it talks. busy_p: chance the channel is busy at each check."""
    def __init__(self, busy_p, airtime_ms, hold_air=True):
        self.busy_p, self.airtime_ms, self.hold_air = busy_p, airtime_ms, hold_air
        self.lbt_waits = 0.0
    async def send_packet(self, pkt, wait_for_ack=False, radio_id=None):
        for attempt in range(LBT_ATTEMPTS):
            if random.random() < self.busy_p:          # channel busy: back off, check again
                back = random.uniform(0.05, 0.25)
                self.lbt_waits += back
                await asyncio.sleep(back)
                continue
            if self.hold_air:
                await asyncio.sleep(self.airtime_ms / 1000.0)   # on air, lock held
            return True
        return False                                   # gave up after all attempts

def make_engine(modem):
    eng = E.RepeaterHandler.__new__(E.RepeaterHandler)
    eng.tx_delay_factor = float(os.environ.get("SIM_FLOOD_F", "1.0"))
    eng.direct_tx_delay_factor = 0.5
    eng.use_score_for_tx = False
    eng.airtime_mgr = AirtimeManager({"radio": RADIO}, max_airtime_per_minute=60000)   # duty cycle off, to isolate timing
    class Budgets:                       # one radio, so every budget lookup is the same manager
        def __init__(self, mgr): self.mgr = mgr
        def for_radio(self, rid): return self.mgr
        def default(self): return self.mgr
    eng.airtime_budgets = Budgets(eng.airtime_mgr)
    eng._egress_gate_radio_ids = lambda pkt: (None,)
    eng._egress_radio_airtime = lambda pkt, rid: eng.airtime_mgr.calculate_airtime(pkt.get_raw_length())
    eng.config = {"delays": {}}
    eng.dispatcher = modem
    eng.sent_flood_count = eng.sent_direct_count = 0
    eng._tx_lock = asyncio.Lock()
    return eng

async def scenario(load, busy_p, hold_air=True, n=25, gap=6.0):
    airtime_ms = AirtimeManager({"radio": RADIO}).calculate_airtime(PKT_LEN)
    modem = Modem(busy_p, airtime_ms, hold_air)
    eng = make_engine(modem)
    stop = False
    async def relays():
        # other traffic through the same radio: Poisson arrivals at `load` (fraction of air time)
        rate = load / (airtime_ms / 1000.0)              # packets per simulated second
        while not stop:
            await asyncio.sleep(random.expovariate(rate))
            pkt = Pkt(flood=random.random() < 0.7)
            delay = eng._calculate_tx_delay(pkt)
            await eng.schedule_retransmit(pkt, delay, airtime_ms, local_transmission=False)
    lat, rnd = [], []
    rt = asyncio.create_task(relays())
    for _ in range(n):
        await asyncio.sleep(gap)
        pkt = Pkt(flood=True)                            # the companion's own message
        t0 = asyncio.get_event_loop().time()
        d = eng._calculate_tx_delay(pkt)
        rnd.append(d)
        task = await eng.schedule_retransmit(pkt, d, airtime_ms, local_transmission=True)
        ok = await task
        t1 = asyncio.get_event_loop().time()
        if ok: lat.append((t1 - t0) / K)                 # back to simulated seconds
    stop = True; rt.cancel()
    return lat, rnd, airtime_ms, modem.lbt_waits / K

def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]

async def main():
    random.seed(7)
    print("Message sent from the companion: time until it goes out (simulated seconds)")
    print("load = share of air time used by other traffic; LBT busy chance follows the load")
    print()
    for label, load in [("quiet", 0.05), ("busy", 0.25), ("very busy", 0.5)]:
        busy = min(0.9, load * 1.5)
        lat, rnd, airtime, lbt = await scenario(load, busy)
        ok = len(lat)
        print(f"{label:10s} load {load:.0%}  airtime {airtime:.0f} ms  delivered {ok}/25")
        print(f"           median {statistics.median(lat):.2f} s   p90 {pct(lat, .9):.2f} s   "
              f"random delay alone (median) {statistics.median(rnd):.2f} s   "
              f"LBT waiting (mean per message) {lbt/25:.2f} s")
    print()
    print("Same loads, but the radio reports success as soon as it has the packet (no air-time wait):")
    for label, load in [("quiet", 0.05), ("busy", 0.25), ("very busy", 0.5)]:
        lat, rnd, airtime, lbt = await scenario(load, min(0.9, load * 1.5), hold_air=False)
        print(f"{label:10s} median {statistics.median(lat):.2f} s   p90 {pct(lat, .9):.2f} s")

asyncio.run(main())
