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
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
