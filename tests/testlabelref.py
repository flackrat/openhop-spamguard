# Labels in the evidence log say when and on which channel the marked message was heard, and a replay gives a
# Not spam answer the same trust it gives on the Pi, from the moment it was given. All names and texts are made up.
import logging, time, tempfile, sys, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

# --- the engine writes the message's time and channel on every kind of label
m=mock(); g=guard(m, floodguard=False, known_min_msgs=5)
rec=[]; g.ev=lambda r: rec.append(r)
m.add("Visitor Q1","Is the club net on tonight?",["C1","DE"],ago=120)
m.add("Visitor Q2","Cheap watches at q-watches.example",["C1","DE"],ago=90)
g.poll_once()
ev={e.sender:e for e in g.events}
e1,e2=ev["Visitor Q1"],ev["Visitor Q2"]
g.action("not_spam",{"sender":e1.sender,"text":e1.text,"packet":e1.packet,"channel":e1.channel,"matched":None})
g.action("label",{"sender":e1.sender,"text":e1.text,"packet":e1.packet,"label":"not_spam"})
g.action("mark_spam",{"sender":e2.sender,"text":e2.text,"packet":e2.packet})
labels=[r for r in rec if r.get("type")=="label"]
check(len(labels)==3,"three labels written: %d"%len(labels))
check(all(r.get("channel")=="Public" for r in labels),"each says the channel: %s"%[r.get("channel") for r in labels])
check(abs(labels[0]["msg_ts"]-e1.ts)<1 and abs(labels[2]["msg_ts"]-e2.ts)<1,"and when the message was heard")
check(labels[0]["msg_ts"]<time.time()-60,"which is not the moment it was marked")
rec.clear(); g.action("label",{"sender":"Nobody Heard","text":"never seen here","label":"spam"})
r=[r for r in rec if r.get("type")=="label"][0]
check("msg_ts" not in r and "channel" not in r,"a label for a message it never heard adds nothing made up")

# --- a replay: Not spam on a held message trusts that name on that channel from then on
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import replay
T=1790000000.0
def burst(start, n, tag):
    return [{"type":"msg","ts":start+i*20,"sender":"Newsdesk Q","text":f"Headline {tag} {i}: river level update","channel":"Public",
             "path":["C1","DE"],"packet":f"p{tag}{i}"} for i in range(n)]
msgs=burst(T,25,"a")+burst(T+7200,25,"b")
for x in msgs: x["_label"]=None
held_a=lambda caught,tag: sum(1 for i,x in enumerate(msgs) if x["packet"].startswith("p"+tag) and caught.get(f"r{i}",(None,))[0])
caught,_=replay.run([dict(x) for x in msgs],{"level":50},{},quiet_step=60)
check(held_a(caught,"a")>0 and held_a(caught,"b")>0,"unmarked: both bursts are held in part")
mark={"type":"label","label":"not_spam","sender":"Newsdesk Q","text":msgs[20]["text"],"packet":msgs[20]["packet"],
      "caught_by":"budget:x","ts":T+3600,"channel":"Public","msg_ts":msgs[20]["ts"]}
caught2,g2=replay.run([dict(x) for x in msgs],{"level":50},{},quiet_step=60,marks=[mark])
check(held_a(caught2,"a")==held_a(caught,"a"),"before the answer nothing changes")
check(held_a(caught2,"b")==0,"after it the name is trusted there and the next burst passes: %d"%held_a(caught2,"b"))
check("Public" in (g2.trust_on.get("Newsdesk Q") or {}),"trusted on that channel only")
old=dict(mark); old.pop("channel"); old.pop("msg_ts")
caught3,_=replay.run([dict(x) for x in msgs],{"level":50},{},quiet_step=60,marks=[old])
check(held_a(caught3,"b")==0,"an older label without a channel is matched to its message")
plain=dict(mark); plain.pop("caught_by")
caught4,_=replay.run([dict(x) for x in msgs],{"level":50},{},quiet_step=60,marks=[plain])
check(held_a(caught4,"b")==held_a(caught,"b"),"a plain Fine label on the Messages page doesn't trust anyone, as on the Pi")
# a later spam mark on that name ends the trust, on the Pi and in a replay
spam={"type":"label","label":"spam","sender":"Newsdesk Q","text":msgs[30]["text"],"packet":msgs[30]["packet"],"ts":T+5400,"by":"label"}
caught5,g5=replay.run([dict(x) for x in msgs],{"level":50},{},quiet_step=60,marks=[mark,spam])
check(held_a(caught5,"b")==held_a(caught,"b") and not g5.trust_on.get("Newsdesk Q"),"a replay: the spam mark ends it")
m=mock(); g=guard(m, floodguard=False)
g.trust_on["Newsdesk Q"]={"Public":time.time()-3600}; g.allow_senders.add("Everywhere Q")
r=g.action("label",{"sender":"Newsdesk Q","text":"Cheap watches at q-watches.example","label":"spam"})
check("Newsdesk Q" not in g.trust_on and "no longer trusted" in str(r),"on the Pi: a spam mark ends trust from a Not spam tap: %s"%r)
g.action("label",{"sender":"Everywhere Q","text":"Cheap watches at q-watches.example","label":"spam"})
check("Everywhere Q" in g.allow_senders,"trust you gave everywhere from People is left for you to take back")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
