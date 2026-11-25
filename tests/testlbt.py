# openHop's listen-before-talk readings: how often a send waited for a clear channel, shown on the FloodGuard
# page and never acted on. Hidden when no send has waited (listen-before-talk off). Made-up packets only.
import sys, time, logging, json
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g=guard(mock()); g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":32}
now=time.time()
def send(ts,tries,busy,route=1,sent=True):
    g.fg_observe({"timestamp":ts,"length":40,"route":route,"type":5,"transmitted":sent,"original_path":["A7"],
                  "lbt_attempts":tries,"lbt_channel_busy":busy,"rssi":-90,"snr":5,"rx_radio_id":"r0"})
for i in range(20): send(now-1000+i,0,False)
check(g.lbt_view(now) is None,"no send waited: nothing shown (listen-before-talk may be off)")
check(g.fg_breakdown(now)["lbt"] is None,"and the breakdown has no line")
before=(g.fg.get("acting"),g.fg.get("limit"),sorted(g.blocks))
for i in range(10): send(now-500+i,2,True)
v=g.lbt_view(now)
check(v and v["sends"]==30 and v["waited"]==10 and v["share"]==33,"waits counted: %s"%v)
check(v["most_tries"]==3,"tries are openHop's retries plus the first")
check(g.fg_breakdown(now)["lbt"]==v,"on the FloodGuard breakdown")
check((g.fg.get("acting"),g.fg.get("limit"),sorted(g.blocks))==before,"FloodGuard doesn't act on it")
check(not g.blocks,"nothing blocked")
g2=guard(mock())
g2.fg_observe({"timestamp":now,"length":40,"route":1,"type":5,"transmitted":True,"original_path":[]})
check(g2.lbt_view(now) is None,"an older openHop without these fields: nothing shown, no error")
g2.fg_observe({"timestamp":now+1,"length":40,"route":1,"type":5,"transmitted":True,"lbt_attempts":"x","lbt_channel_busy":True})
check(True,"a bad value doesn't break anything")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
