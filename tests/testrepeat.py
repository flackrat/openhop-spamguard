# One name posting the same line over and over: the first few copies go out, further copies of that line
# from that name are stopped (even though the name is "known"), anything new they say still goes out,
# and other people quoting the line are unaffected. The copy-paste guard stays quiet until it stops a copy.
# All names and messages are made up.
import sys, logging, os, json, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m, evidence_log=True, evidence_dir=os.path.join(TMP,"ev_rep"), known_min_msgs=3)
g.apply_settings({"mode":"protect"})
check(int(sg.DEFAULT_CONFIG["known_min_msgs"])==3,"a name needs 3 genuine messages to count as known by default")
for i,t in enumerate(["Morning all from the hill","Nice and clear today","Anyone near the canal?","Off for lunch now"]):
    m.add("Quarry Pete",t,["4C","2F"],ago=3000-i*60)
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=2500)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Quarry Pete"),"regular with several messages is known")
# Pete starts repeating one line
for i in range(5):
    m.add("Quarry Pete","@[Hilltop Hiker] please answer me",["4C","2F"],ago=200-i*20)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
reps=[b for b in g.blocks.values() if b["kind"]=="repeat"]
check(len(reps)==1 and reps[0].get("who")=="Quarry Pete","repeat block for that name: "+str(reps))
check(m.decide("Quarry Pete","@[Hilltop Hiker] please answer me",["4C","2F"])=="drop","another copy from Pete is dropped although he is known")
check(m.decide("Quarry Pete","Sorry everyone, signing off",["4C","2F"])=="allow","something new from Pete still goes out")
check(m.decide("Hilltop Hiker","Pete said please answer me, I did",["A7","2F"])=="allow","someone else quoting it is unaffected")
acts=[a["msg"] for a in g.activity]
check(any("more copies of" in a and "Quarry Pete" in a for a in acts),"noted in Activity")
# A couple of repeats (resending once because nobody answered) are fine
m2=mock(); g2=guard(m2); g2.apply_settings({"mode":"protect"})
for i in range(3): m2.add("Canal Boat Ted","Is anyone hearing me tonight?",["B1","2F"],ago=300-i*60)
g2.poll_once(); g2.poll_once()
check(not any(b["kind"]=="repeat" for b in g2.blocks.values()),"three copies are allowed")
# Very short lines ('test') never trigger it
m3=mock(); g3=guard(m3); g3.apply_settings({"mode":"protect"})
for i in range(6): m3.add("Radio Ruth","test",["C3","2F"],ago=300-i*30)
g3.poll_once(); g3.poll_once()
check(not any(b["kind"]=="repeat" for b in g3.blocks.values()),"short test messages never trigger it")
# Turned off
m4=mock(); g4=guard(m4, repeat_guard=False); g4.apply_settings({"mode":"protect"})
for i in range(6): m4.add("Quarry Pete","@[Hilltop Hiker] please answer me",["4C","2F"],ago=200-i*20)
g4.poll_once(); g4.poll_once()
check(not any(b["kind"]=="repeat" for b in g4.blocks.values()),"setting off: nothing blocked")
# Quiet copy guard: a normal long message sets one up silently
m5=mock(); g5=guard(m5); g5.apply_settings({"mode":"protect"})
m5.add("Hilltop Hiker","Is the repeater on the church tower back up yet?",["A7","2F"],ago=100)
g5.poll_once(); g5.poll_once()
check(any(b.get("source")=="dedupe" for b in g5.blocks.values()),"copy guard set up")
check(not any("Started blocking" in a["msg"] for a in g5.activity),"but nothing in Activity yet")
m5.add(rname(),"Is the repeater on the church tower back up yet?",["9D","2F"],ago=0)
g5.poll_once(); g5.poll_once()
check(any("Stopped a copy" in a["msg"] for a in g5.activity),"noted once it stops a copy: "+str([a["msg"] for a in g5.activity][:3]))
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
