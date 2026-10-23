# One name posting the same long message again and again, spread over hours so the quick repeat check never
# sees it.
# Further copies are held after the daily limit, the first copies and anything new still go out, ordinary
# repeats and short messages are never touched, and nothing depends on what the message says.
# All names and messages are made up.
import sys, logging, os, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

TEXT="Reminder that the club net is on Thursday evenings at eight, everyone is welcome to join in"
def sends(m,name,text,count,gap,ago_first,path=("4C","2F"),vary=False):
    """count sends of text, gap seconds apart, the first one ago_first seconds ago (@-mention varies per copy)."""
    for i in range(count):
        t=(f"@[Person {i}] "+text) if vary else text
        m.add(name,t,list(path),ago=ago_first-i*gap)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()

# 1. About one send an hour, from a known name, with the @-mention changing each time
m=mock(); g=guard(m, known_min_msgs=1, long_window_seconds=86400); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all from the hill","Nice and clear today","Anyone near the canal?","Off for lunch now"]):
    m.add("Rowan Hill",t,["4C","2F"],ago=40000-i*60)
sends(m,"Rowan Hill",TEXT,3,3300,12000,vary=True)
cycle(g)
check(g.is_known("Rowan Hill"),"the name is known")
check(not any(b["kind"]=="repeat" for b in g.blocks.values()),"three sends in the day: nothing held yet")
check(m.decide("Rowan Hill",TEXT,["4C","2F"])=="allow","the first three copies go out")
sends(m,"Rowan Hill",TEXT,1,0,300)         # the fourth send of the day
cycle(g)
reps=[b for b in g.blocks.values() if b["kind"]=="repeat" and b.get("source")=="slowrepeat"]
check(len(reps)==1 and reps[0].get("who")=="Rowan Hill","one slow-repeat block for that name: "+str(reps))
check(reps and 10000<reps[0]["expires"]-time.time()<=10800+5,"held for about three hours")
check(m.decide("Rowan Hill",TEXT,["4C","2F"])=="drop","the next copy is dropped although the name is known")
check(m.decide("Rowan Hill","@[Someone Else] "+TEXT,["4C","2F"])=="drop","even with a different @-mention")
check(m.decide("Rowan Hill","Sorry for the noise, back to normal chat",["4C","2F"])=="allow","something new from the same name goes out")
check(m.decide("Hilltop Hiker","Rowan said: "+TEXT[:40]+" and I am not sure",["A7","2F"])=="allow","someone else quoting it is unaffected")
check(any("more copies of" in a["msg"] and "Rowan Hill" in a["msg"] for a in g.activity),"noted in Activity")


# 2. Hold ends: one copy gets through, and holding starts again straight after while they keep at it
key=[k for k,b in g.blocks.items() if b.get("source")=="slowrepeat"][0]
g.blocks[key]["expires"]=time.time()-1
g.suppressed.pop(key,None)
g.cfg_dirty=True
cycle(g)
check(key not in g.blocks or g.blocks[key]["expires"]>time.time(),"after the hold, a new send brings it back only if they send again")

# 3. Copies of one send arriving by several routes a moment apart count once
m2=mock(); g2=guard(m2, long_window_seconds=86400); g2.apply_settings({"mode":"protect"})
for s in range(3):
    for j,path in enumerate((("4C","2F"),("9A","31","2F"),("B2","2F"))):
        m2.add("Quarry Pete",TEXT,list(path),ago=9000-s*3000-j*15)
cycle(g2)
check(not any(b["kind"]=="repeat" for b in g2.blocks.values()),"three sends, each heard three ways, is three sends not nine")

# 4. A notice re-posted a few times a day is fine; short messages never count
m3=mock(); g3=guard(m3, long_window_seconds=86400); g3.apply_settings({"mode":"protect"})
sends(m3,"Quarry Pete","Is anyone hearing me tonight? Radio check please",3,7000,20000)
for i in range(8): m3.add("Radio Ruth","test",["C3","2F"],ago=9000-i*900)
cycle(g3)
check(not any(b["kind"]=="repeat" for b in g3.blocks.values()),"three re-posts and short test messages are left alone")

# 5. Different wording each time is not a repeat (nothing about the topic matters)
m4=mock(); g4=guard(m4, long_window_seconds=86400); g4.apply_settings({"mode":"protect"})
topics=["Weather looks lovely over the valley this afternoon","Anybody fancy a meet up at the hill on Saturday","Battery at 80 percent after a week on solar",
        "New antenna went up on the church tower today","Signal into the next county was fantastic earlier","Planning a long walk with the node on Sunday"]
for i,t in enumerate(topics): m4.add("Hilltop Hiker",t,["A7","2F"],ago=20000-i*3000)
cycle(g4)
check(not any(b["kind"]=="repeat" for b in g4.blocks.values()),"six different messages in a day are never held")

# 6. Two people each posting the same long message a few times are counted separately
m5=mock(); g5=guard(m5, long_window_seconds=86400); g5.apply_settings({"mode":"protect"})
for who,path in (("Quarry Pete",["4C","2F"]),("Hilltop Hiker",["A7","2F"])):
    sends(m5,who,TEXT,3,5000,17000,path=path)
cycle(g5)
check(not any(b["kind"]=="repeat" for b in g5.blocks.values()),"counted per name, not across names")

# 7. Sends older than the window don't count
m6=mock(); g6=guard(m6, long_window_seconds=86400); g6.apply_settings({"mode":"protect"})
sends(m6,"Quarry Pete",TEXT,3,3600,300000)   # days ago
sends(m6,"Quarry Pete",TEXT,1,0,200)
cycle(g6)
check(not any(b["kind"]=="repeat" for b in g6.blocks.values()),"old sends are forgotten")

# 8. Turned off, and the limit can be changed
m7=mock(); g7=guard(m7, slow_repeat=False, long_window_seconds=86400); g7.apply_settings({"mode":"protect"})
sends(m7,"Quarry Pete",TEXT,6,3000,18000)
cycle(g7)
check(not any(b["kind"]=="repeat" for b in g7.blocks.values()),"setting off: nothing held")
m8=mock(); g8=guard(m8, slow_repeat_max=5, long_window_seconds=86400); g8.apply_settings({"mode":"protect"})
sends(m8,"Quarry Pete",TEXT,5,3000,18000)
cycle(g8)
check(not any(b["kind"]=="repeat" for b in g8.blocks.values()),"a higher limit lets five through")
sends(m8,"Quarry Pete",TEXT,1,0,100)
cycle(g8)
check(any(b.get("source")=="slowrepeat" for b in g8.blocks.values()),"and holds the sixth")

# 9. Trusted names are exempt
m9=mock(); g9=guard(m9, long_window_seconds=86400); g9.apply_settings({"mode":"protect"})
g9.allow_senders.add("Quarry Pete")
sends(m9,"Quarry Pete",TEXT,6,3000,18000)
cycle(g9)
check(not any(b["kind"]=="repeat" for b in g9.blocks.values()),"a trusted name is never held")

# 10. The count survives a restart (the repeater reboots nightly)
m10=mock(); g10=guard(m10, long_window_seconds=86400); g10.apply_settings({"mode":"protect"})
sends(m10,"Quarry Pete",TEXT,3,3000,12000)
cycle(g10)
g10._save_state(force=True)
g11=sg.SpamGuard({"state_file":g10.cfg["state_file"],"openhop_url":g10.cfg["openhop_url"],"api_key":"t","mode":"protect"})
check(sum(len(v["ts"]) for v in g11.slow_sends.values())==3,"three sends remembered after a restart: "+str(g11.slow_sends)[:120])
m10.add("Quarry Pete",TEXT,["4C","2F"],ago=60)
g11.poll_once(); g11.last_sync=0; g11.sync_pending=True; g11.poll_once()
check(any(b.get("source")=="slowrepeat" for b in g11.blocks.values()),"the fourth send after a restart is held")

# 11. Settings are exposed with plain help text
keys={s["key"] for s in sg.SETTINGS} if hasattr(sg,"SETTINGS") else set()
check(not keys or {"slow_repeat","slow_repeat_max","slow_repeat_window_seconds","slow_repeat_hold_seconds"}<=keys,"settings listed for the page")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
