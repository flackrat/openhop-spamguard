# The experimental text learner: off unless switched on, learns only from your own marks and ordinary chat,
# never acts on one message, holds only the shared part of several spam-like messages from one name, and
# only in the "record only" mode by default. All names and messages are made up.
import sys, logging, os, time, random, json
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()

rnd=random.Random(4)
WORDS="rain wind hill road cold bright morning evening signal good clear radio mast tower garden coffee lunch walk dog club net thursday meeting later again nice quiet busy slow fast north south east west village market bridge river".split()
def chat(): return " ".join(rnd.choice(WORDS) for _ in range(rnd.randint(5,10)))+" today"
SPAM0="Beware, bargainmesh.example is a fake shop, shopmesh.example is the real one, never buy from bargainmesh.example"
SPAM1="Warning everyone: bargainmesh.example is a fake shop run by a fraud, the real shop is shopmesh.example"
SPAM2="bargainmesh.example is a fake shop, please do not use it, go to shopmesh.example instead, they are honest"
REPLY="I think that is right, that bargainmesh.example place looked odd to me too when I read about it earlier"

def fresh(**cfg):
    m=mock(); g=guard(m, known_min_msgs=1, long_window_seconds=86400, **cfg)
    g.apply_settings({"mode":"protect"})
    for i in range(420):
        m.add(f"Regular {i%9}",chat(),["4C","2F"],ago=80000-i*150)
    return m,g

# 1. Off by default: nothing is learned from chat, nothing is held
m,g=fresh()
g._sense_label("k1",SPAM0,"spam")
m.add("Pedlar Sam",SPAM1,["4C","2F"],ago=600); m.add("Pedlar Sam",SPAM2,["4C","2F"],ago=300)
cycle(g)
check(g.sense.n[0]==0,"switched off: ordinary chat is not learned")
check(not any(b.get("source")=="sense" for b in g.blocks.values()),"switched off: nothing held")
check(g.cfg["text_sense"] is False and g.cfg["text_sense_log_only"] is True,"off, and record-only, by default")

# 2. Switched on, record only: learns, notices, records, holds nothing
m,g=fresh(text_sense=True)
cycle(g)
check(g.sense.n[0]>=300,"learned what ordinary chat looks like: "+str(g.sense.n))
g._sense_label("k1",SPAM0,"spam")
check(g.sense.ready(),"ready once it has seen chat and one mark")
m.add("Pedlar Sam",SPAM1,["4C","2F"],ago=600)
cycle(g)
check(not any(b.get("source")=="sense" for b in g.blocks.values()),"one spam-like message is never enough")
m.add("Pedlar Sam",SPAM2,["4C","2F"],ago=300)
cycle(g)
check(not any(b.get("source")=="sense" for b in g.blocks.values()),"record only: nothing held")
check(g.stats.get("sense_would_hold",0)==1,"record only: noted what it would have held: "+str(g.stats.get("sense_would_hold")))
check(m.decide("Pedlar Sam",SPAM1,["4C","2F"])=="allow","record only: the message still goes out")

# 3. Active mode holds the shared part, for that name only
m,g=fresh(text_sense=True, text_sense_log_only=False)
cycle(g)
g._sense_label("k1",SPAM0,"spam")
m.add("Pedlar Sam",SPAM1,["4C","2F"],ago=600); m.add("Pedlar Sam",SPAM2,["4C","2F"],ago=300)
cycle(g)
bl=[b for b in g.blocks.values() if b.get("source")=="sense"]
check(len(bl)==1 and bl[0]["kind"]=="repeat" and bl[0].get("who")=="Pedlar Sam","one hold, against that name: "+str(bl))
check(bl and "bargainmesh.example" in bl[0]["value"] and len(bl[0]["value"])>=14,"it holds the part they share: "+str(bl and bl[0]["value"]))
check(m.decide("Pedlar Sam","Hot tip! bargainmesh.example is a fake shop, honest "+chat(),["4C","2F"])=="drop","a third rewording by the same name is held")
check(m.decide("Pedlar Sam",chat(),["4C","2F"])=="allow","ordinary chat from the same name goes out")
check(m.decide("Regular 3","bargainmesh.example is a fake shop, so I heard",["4C","2F"])=="allow","another name saying it is not touched")

# 4. A person talking about it once is not held, and one spam-like message alone is not held
m,g=fresh(text_sense=True, text_sense_log_only=False)
cycle(g)
g._sense_label("k1",SPAM0,"spam")
m.add("Regular 2",REPLY,["4C","2F"],ago=300)
cycle(g)
check(not any(b.get("source")=="sense" for b in g.blocks.values()),"someone replying once is not held")

# 5. Your marks can be taken back, and a "fine" mark teaches it the other way
m,g=fresh(text_sense=True)
cycle(g)
g._sense_label("k1",SPAM0,"spam")
hi=g.sense.score(SPAM1)
g._sense_label("k1",SPAM0,"none")
check(g.sense.n[1]==0 and g.sense.score(SPAM1)<hi,"clearing a mark takes the lesson back")
g._sense_label("k2",REPLY,"not_spam")
check(g.sense_learned.get("k2")=="not_spam","a fine mark is learned too")

# 6. Kept across a restart as counts, never as messages
m,g=fresh(text_sense=True)
cycle(g)
g._sense_label("k1",SPAM0,"spam")
g._save_state(force=True)
raw=open(g.file_cfg.get("state_file",g.cfg["state_file"]) if hasattr(g,"file_cfg") else g.cfg["state_file"]).read()
check("bargainmesh" not in raw,"no message text in the saved state")
m2=mock(); g2=guard(m2, state_file=g.cfg["state_file"], text_sense=True)
check(g2.sense.n[1]==g.sense.n[1] and g2.sense_learned==g.sense_learned,"model and marks come back after a restart")
g2.sense.load({"c":"nonsense"})
check(g2.sense.n==[0.0,0.0],"a damaged model resets instead of crashing")

# 7. Short or mention-only messages are ignored
m,g=fresh(text_sense=True)
cycle(g)
before=g.sense.n[0]
m.add("Regular 1","ok thanks",["4C","2F"],ago=100)
cycle(g)
check(g.sense.n[0]==before,"messages under 14 characters are skipped")

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
