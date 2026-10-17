# Interference watch: learns this site's normal noise floor from openHop's samples, reports when the noise
# stays well above it (a carrier that never stops, such as faulty temporary traffic lights, or jamming),
# records each episode, and ignores short spikes and small drifts. Simulated clock; all data made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
CLOCK=[time.time()-3*86400]; _real=time.time; time.time=lambda: CLOCK[0]
random.seed(5)

def run(g, minutes, noise):
    """noise(minute) -> dBm; one openHop sample every 30 s, SpamGuard checks every minute."""
    for i in range(minutes):
        rows=[]
        for half in (0,30):
            CLOCK[0]+=30
            rows.append({"timestamp":CLOCK[0],"noise_floor_dbm":round(noise(i)+random.gauss(0,1.2),1)})
        g.nf_ingest(rows); g.jam_decide(CLOCK[0])

m=mock(); g=guard(m, floodguard=False); g.radio={"frequency":869.525,"spreading_factor":8,"bandwidth":62500,"coding_rate":8}
run(g, 60*4, lambda i:-118)
check(g.jam_status()["learning"],"learning for the first hours")
run(g, 60*20, lambda i:-118)
st=g.jam_status()
check(not st["learning"] and abs(st["baseline"]+118)<1, f"learns this site's normal noise: {st['baseline']}")
check(not st["since"],"no interference on a normal day")

run(g, 3, lambda i:-92)               # a three-minute burst (someone keying up nearby)
check(not g.jam.get("since"),"a short burst isn't interference")
run(g, 60, lambda i:-113)              # a small drift of 5 dB (weather, a new device indoors)
check(not g.jam.get("since"),"a small rise isn't reported")
run(g, 30, lambda i:-118)

run(g, 4, lambda i:-98)                # the traffic lights arrive: +20 dB, always on
check(not g.jam.get("since"),"waits five minutes")
run(g, 6, lambda i:-98)
check(g.jam.get("since"),"reports a carrier that stays on")
note=g.activity[0]["msg"]
check("Interference" in note and "869.525 MHz" in note and " dB above normal" in note, f"says so in Activity: {note[:90]}")
st=g.jam_status()
check(8<=st["range"]<=13, f"says how much range is left (about 10% at +20 dB): {st['range']}%")
hw=g.health()
check(any("Interference" in w for w in hw.get("warnings",[])), "and on Health")
run(g, 36, lambda i:-98)
run(g, 8, lambda i:-118)
check(g.jam.get("since"),"not over the moment it goes quiet")
run(g, 8, lambda i:-118)
check(not g.jam.get("since"),"over after ten quiet minutes")
eps=g.jam_status()["episodes"]
check(len(eps)==1 and 18<=eps[0]["peak_db"]<=24 and 40<=(eps[0]["end"]-eps[0]["start"])/60<=55, f"the episode is recorded with its times and level: {eps}")
check(any("Interference over" in a["msg"] for a in g.activity),"and its end noted")
check(abs(g.jam_status()["baseline"]+118)<1.5,"the interference hours don't move what counts as normal")

g._save_state(force=True)
g2=sg.SpamGuard(dict(g.file_cfg))
check(len(g2.jam_status()["episodes"])==1,"episodes survive a restart")

g3=guard(mock(), floodguard=False, interference_watch=False)
run(g3, 60*25, lambda i:-118); run(g3, 30, lambda i:-90)
check(not g3.jam.get("since"),"off: nothing reported")
time.time=_real
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
