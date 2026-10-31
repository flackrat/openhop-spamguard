# A name only counts as known once it has sent enough genuine messages AND has been heard for a minimum time,
# so posting a few harmless messages in a row can't earn trust within minutes. Made-up names.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

check(any(m["key"]=="known_min_minutes" for m in sg.SETTINGS_META),"shown as a setting")
check(sg.DEFAULT_CONFIG["known_min_minutes"]==60,"an hour by default")
m=mock(); g=guard(m, known_min_msgs=3, known_min_minutes=60); g.apply_settings({"mode":"protect"})
# three genuine messages in ten minutes: enough messages, not enough time
for i in range(3):
    m.add("Quick Quentin",f"Morning everyone number {i}",["A1","B2"],ago=900-i*300)
# three messages over two hours
for i in range(3):
    m.add("Steady Sue",f"Afternoon all, number {i}",["C3"],ago=6000-i*2400)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.known["Quick Quentin"][2]>=3, "Quentin has sent enough messages")
check(not g.is_known("Quick Quentin"), "but not been heard for long enough, so is not known yet")
check(g.is_known("Steady Sue"), "Sue has both, so is known")
check("Quick Quentin" not in g.known_list() and "Steady Sue" in g.known_list(), "only Sue is written to openHop's let-through list")
k=g.status()["known"]
check(k["min_minutes"]==60 and k["learning"]>=1, f"the page can show the wait: {k['min_minutes']} min, {k['learning']} still learning")
# an hour later he is known (his first message was heard more than an hour ago)
g.known["Quick Quentin"][0]-=3600
check(g.is_known("Quick Quentin"), "once enough time has passed he is known")
# trusted names are always known, and 0 turns the wait off
g.allow_senders.add("Trusted Tess"); check(g.is_known("Trusted Tess"), "trusted names always count")
g2=guard(mock(), known_min_msgs=1, known_min_minutes=0); g2.known["New Nick"]=[time.time(),time.time(),1]
check(g2.is_known("New Nick"), "with the wait set to 0 a name is known at once")
# known names written before this setting existed have old first-heard times, so stay known
g3=guard(mock(), known_min_msgs=3, known_min_minutes=60); g3.known["Old Oscar"]=[time.time()-10*86400,time.time()-3600,40]
check(g3.is_known("Old Oscar"), "names already known before the setting stay known")
# forgetting one says what it takes to count again
g.known["Steady Sue"]=[time.time()-9000,time.time(),9]
r=g.action("forget_known",{"name":"Steady Sue"}) if hasattr(g,"action") else {}
check("at least 60 minutes" in str(r.get("message","")), "forgetting one says what it takes to count again: "+str(r.get("message")))
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
