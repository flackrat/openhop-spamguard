# SpamGuard can't be turned against what people say: a text you block by hand never stops people it knows,
# must be a real chunk of a message (not a word or a name), and can't last for ever. A known person's
# message can't be marked as spam. Bots and made-up names are still stopped. All names and messages are made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m, known_min_msgs=3); g.apply_settings({"mode":"protect"})
for i,t in enumerate(["Morning all from the hill","Nice and clear today","Anyone near the canal?"]):
    m.add("Quarry Pete",t,["4C","2F"],ago=3000-i*60)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.is_known("Quarry Pete"),"regular is known")
# too short: a word or a name
for t in ("vote","Quarry Pete","no to masts"):
    try: g.action("block_text",{"text":t}); check(False,"short text refused: "+t)
    except ValueError: check(True,"")
g.action("block_text",{"text":"we should vote against the new mast"})
g.last_sync=0; g.sync_pending=True; g.poll_once()
check(m.decide("Quarry Pete","I think we should vote against the new mast",["4C","2F"])=="allow","a known person can still say it")
check(m.decide(rname(),"we should vote against the new mast",["9D","2F"])=="drop","a made-up name sending it is still stopped")
b=[x for x in g.blocks.values() if x["kind"]=="text" and x.get("source")=="manual"][0]
check(not g.block_matches(b, sg.Event(time.time(),["4C","2F"],"Quarry Pete","we should vote against the new mast","Public")),"SpamGuard's own view agrees")
# never for ever
key=[k for k,x in g.blocks.items() if x is b][0]
try: g.action("extend",{"key":key,"permanent":True}); check(False,"text can't be kept for ever")
except ValueError: check(True,"")
g.action("extend",{"key":key,"seconds":30*86400})
check(b["expires"]-time.time()<=sg.TEXT_BLOCK_MAX_SECONDS+5,"extending stops at a week")
g.action("block_text",{"text":"another long message to block here","ttl_seconds":sg.PERMANENT_SECONDS})
b2=g.blocks[sg.text_key("another long message to block here")]
check(b2["expires"]-time.time()<=sg.TEXT_BLOCK_MAX_SECONDS+5,"asking for 'until I remove it' still ends within a week")
# known person's message can't be marked as spam
try: g.action("mark_spam",{"text":"Morning all from the hill, lovely day","sender":"Quarry Pete"}); check(False,"known person not markable")
except ValueError: check(True,"")
g.action("mark_spam",{"text":"Cheap crypto signals join the group today","sender":rname()})
check(any(x.get("reason")=="Marked as spam by you" for x in g.blocks.values()),"unknown name can still be marked")
# repeater blocks can still be kept (they are about where traffic comes from, not what it says)
g.action("block_hop",{"hop":"9D"}); hk=[k for k,x in g.blocks.items() if x["kind"]=="hop"][0]
g.action("extend",{"key":hk,"permanent":True})
check(g.blocks[hk]["expires"]-time.time()>sg.TEXT_BLOCK_MAX_SECONDS,"repeater block can be kept")
# a repeater block that stops everyone (known people too) can't be kept for ever either
g.action("block_hop",{"hop":"7E","match":"contains","ttl_seconds":sg.PERMANENT_SECONDS})
g.poll_once()
check(g.blocks["hop:7E"]["expires"]-time.time()<=sg.TEXT_BLOCK_MAX_SECONDS+60,"'anything passing through' ends within a week")
try: g.action("extend",{"key":"hop:7E","permanent":True}); check(False,"can't keep a block that stops everyone")
except ValueError: check(True,"")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
