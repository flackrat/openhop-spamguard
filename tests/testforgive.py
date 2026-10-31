# Removing a duplicate block by hand (or clearing automatic blocks) forgives the copies seen so far, instead
# of switching duplicate checking off for that text: the next copy counts as a first copy again, and copies
# after it are held back as usual. Short duplicate settings really give short rules. A message with no name
# in front is "Unknown" to openHop, so rules about it say so, and "Unknown" is never a known person.
# All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
MSG="Is the repeater on the church tower back up yet?"
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
m.add("Hilltop Hiker",MSG,["A7","2F"],ago=120)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
dk=[k for k,b in g.blocks.items() if b.get("source")=="dedupe"]
check(dk,"copy guard set up after the first message")
g.action("unblock",{"key":dk[0]})
check(dk[0] not in g.suppressed,"not held off for 24 hours")
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(dk[0] not in g.blocks,"not rebuilt from the copies already seen")
time.sleep(0.05); m.add("Canal Boat Ted",MSG,["D8","2F"],ago=0)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
nb=[b for b in g.blocks.values() if b.get("source")=="dedupe"]
check(nb and nb[0].get("sender")=="Canal Boat Ted","the next copy is a first copy again: "+str([(b.get('sender'),b['value']) for b in nb]))
check(m.decide("Canal Boat Ted",MSG,["D8","2F"])=="allow","its sender may re-send")
check(m.decide(rname(),MSG,["9D","2F"])=="drop","copies after it are held back again")
# clear automatic blocks forgives duplicates too
g.action("clear_auto",{})
check(not any(k.startswith("text:") and k in g.suppressed for k in [k for k in g.suppressed]),"clear doesn't hold duplicates off")
# short duplicate settings give short rules
m2=mock(); g2=guard(m2, dedupe_min_chars=5, text_rule_chars=5); g2.apply_settings({"mode":"protect"})
m2.add("Radio Ruth","Hello mesh",["C3","2F"],ago=30)
g2.poll_once(); g2.poll_once()
check(any(b.get("source")=="dedupe" for b in g2.blocks.values()),"a 10-character message gets a duplicate rule when the lengths are set low")
# nameless messages
check(sg.oh_sender("")=="Unknown" and sg.oh_sender("Bob")=="Bob","nameless sender is Unknown for openHop")
g.allow_senders.add("Unknown")
check("Unknown" not in g.known_list(),"Unknown is never written as a known person")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
