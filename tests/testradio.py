# A dead radio: openHop keeps trying to send and every send fails, so Health says the radio isn't
# transmitting. A send getting out again clears it, and one or two failures on a busy channel don't. All data made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def pkt(ts, sent=False, reason=None):
    p={"timestamp":ts,"length":40,"route":1,"type":5,"transmitted":sent,"rssi":0,"snr":0,"original_path":"[]"}
    if reason: p["drop_reason"]=reason
    return p
g=guard(mock()); now=time.time()
g.fg_observe(pkt(now-1000, sent=True))
for i in range(2): g.fg_observe(pkt(now-600+i, reason="TX failed"))
check(g.radio_failing(now)==0, "two failures are not enough")
g.fg_observe(pkt(now-500, reason="TX failed"))
check(g.radio_failing(now)==3, "three failures with nothing sent")
h=g.health()
check(any("radio isn't transmitting" in p for p in h.get("problems",[])), f"Health shows it: {h.get('problems')}")
g.fg_observe(pkt(now-400, sent=True))
check(g.radio_failing(now)==0, "a send getting out clears it")
check(g.radio_failing(now+2000)==0, "old failures age out")
# 6.4.3: some transmits failing (not all), and the Pi's power from vcgencmd
import types
import spamguard as sgmod
g2=guard(mock()); now2=time.time()
for i in range(3): g2.fg_observe(pkt(now2-300+i, reason="TX failed"))
for i in range(10): g2.fg_observe(pkt(now2-200+i, sent=True))
check(g2.send_counts(now2)==(3,10), f"counts: {g2.send_counts(now2)}")
h2=g2.health()
check(any("transmits failed in the last 15 minutes" in w for w in h2.get("warnings",[])), f"intermittent failures warned: {h2.get('warnings')}")
g3=guard(mock())
for i in range(3): g3.fg_observe(pkt(now2-300+i, sent=True))
for i in range(3): g3.fg_observe(pkt(now2-200+i, reason="TX failed"))
check(not any("transmits failed" in w for w in g3.health().get("warnings",[])), "a few failures among many sends are not warned")
real_run=sgmod.subprocess.run
def fake(out):
    return lambda *a, **k: types.SimpleNamespace(stdout=out)
sgmod.subprocess.run=fake("throttled=0x50005\n")
g4=guard(mock()); g4._power=(0.0,None)
check(g4.power_status(now2)["now"] is True, "under-voltage now is read")
check(any("too low right now" in w for w in g4.health().get("warnings",[])), "under-voltage now is warned")
sgmod.subprocess.run=fake("throttled=0x40000\n")
g5=guard(mock())
check(g5.power_status(now2)["now"] is False and g5.power_status(now2)["throttled_since_boot"] is True, "since-boot flag read")
sgmod.subprocess.run=fake("throttled=0x0\n")
g6=guard(mock())
check(not any("power" in w.lower() for w in g6.health().get("warnings",[])), "a healthy Pi gives no power warning")
sgmod.subprocess.run=real_run
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
