# One answer per message (spam or not spam), a To review list that empties as you answer, and taking an answer
# back. All names and messages are made up.
import sys, logging, os, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def body(r,v): return dict({k:r[k] for k in ("sender","text","path","packet","channel","matched","status")},verdict=v)
m=mock()
for i,(n,t) in enumerate([("Hilltop Hiker","Morning all, clear skies up here"),("Sparky Sue","Copy that, loud and clear")]): m.add(n,t,["A7","2F"],ago=1500-i*120)
for i in range(6): m.add(rname(),"FREE PRIZE claim now at the usual place today",["C4","9D","E1"],ago=60-i)
g=guard(m); g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for i in range(4): m.add(rname(),"FREE PRIZE claim now at the usual place today",["C4","9D","E1"])
g.poll_once()
q=g.quarantine({"status":"review"}); c=q["counts"]
check(c["review"]==c["held"]+c["letthrough"] and c["review"]>0,"To review is what was held or missed: "+str(c))
check(q["total"]==sum(c[k] for k in g.Q_STATUSES),"the total counts each message once")
check(g.to_review()==c["review"] and g.status()["to_review"]==c["review"],"the page is told how many are waiting")
r=q["rows"][0]
out=g.give_verdict(body(r,"spam"))
check("Marked as spam" in out["message"],"the answer says what it did: "+out["message"])
q2=g.quarantine({"status":"review"})
check(q2["counts"]["review"]==0 and q2["counts"]["reviewed"]>=r["copies"],"the message and its copies leave To review")
check(any(x["label"]=="spam" for x in g.quarantine({"status":"reviewed"})["rows"]),"and are found under answered")
check(g.to_review()==0,"the waiting count follows straight away")
ca=q2["counts"]
check(sum(ca[k] for k in g.Q_STATUSES)==sum(c[k] for k in g.Q_STATUSES)-ca["reviewed"] and not any(x["label"] for s in ("all",)+g.Q_STATUSES for x in g.quarantine({"status":s})["rows"]),"an answered message is listed under Answered only")
check(q2["total"]+ca["reviewed"]==q["total"],"and the counts still add up")
blocks=[k for k,b in g.blocks.items() if b.get("source")=="manual" and b["kind"]=="text"]
if r["status"]=="letthrough": check(len(blocks)==1,"a missed spam message: copies are stopped from now on")
out=g.give_verdict(body(r,"none"))
check("taken back" in out["message"] and not [k for k,b in g.blocks.items() if b.get("source")=="manual" and b["kind"]=="text"],"taking it back undoes it")
check(g.quarantine({"status":"review"})["counts"]["review"]==c["review"],"and the message is waiting again")

# Not spam on a held message lets it through and trusts the sender; taking it back removes the trust
g.held.append({"ts":time.time(),"sender":"Trail Runner 7","text":"anyone about on the ridge","path":"C4>2F","why":"test","matched":None,"packet":"pk-held"})
out=g.give_verdict({"verdict":"not_spam","sender":"Trail Runner 7","text":"anyone about on the ridge","path":"C4>2F","packet":"pk-held","status":"held"})
check("Trail Runner 7" in g.allow_senders and "trusted" in out["message"],"not spam on a held message trusts the sender")
g.give_verdict({"verdict":"none","sender":"Trail Runner 7","text":"anyone about on the ridge","packet":"pk-held","status":"held"})
check("Trail Runner 7" not in g.allow_senders,"taking it back removes the trust")
# Not spam on a delivered message only records the answer
out=g.give_verdict({"verdict":"not_spam","sender":"Hilltop Hiker","text":"Morning all, clear skies up here","packet":"pk-x","status":"genuine"})
check("Hilltop Hiker" not in g.allow_senders,"not spam on a delivered message changes nothing else")
# Spam on a known person never blocks their words
before=set(g.blocks)
g.allow_senders.add("Sparky Sue")
g.give_verdict({"verdict":"spam","sender":"Sparky Sue","text":"Copy that, loud and clear","path":"A7>2F","packet":"pk-y","status":"genuine"})
check(set(g.blocks)==before,"spam on a known person adds no block on what they said")
for bad in ({}, {"verdict":"maybe"}, None):
    try: g.give_verdict(bad); refused=False
    except ValueError: refused=True
    check(refused,"an unknown answer is refused")
# Only chosen messages when the Overview sends a list of them
pk=[x["packet"] for x in g.quarantine({"status":"all"})["rows"]][:1]
check(len(g.quarantine({"status":"all","packets":pk,"group":False})["rows"])==1,"a chosen set of messages can be opened")
ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check('data-page="held"' not in ui and "liveBox" not in ui and "lkList" not in ui,"message lists live only in Messages")
check("Label as" not in ui and "spoofed name" not in ui and "borrowed name" not in ui,"one set of words")
# A campaign that changes a little each time: answering one answers its reworded copies too
m5=mock()
for i in range(6): m5.add(rname(),"FREE PRIZE claim now at the usual place today ref "+rname(5),["C4","9D","E1"],ago=60-i)
m5.add("Hilltop Hiker","Morning all, clear skies up here on the ridge",["A7","2F"],ago=30)
g5=guard(m5); g5.poll_once(); g5.poll_once()
q5=g5.quarantine({"status":"review"}); n5=q5["counts"]["review"]
if n5>=2:
    g5.give_verdict(body(q5["rows"][0],"spam"))
    q6=g5.quarantine({"status":"review"})
    check(q6["counts"]["review"]==0,f"the reworded copies leave To review too ({n5} -> {q6['counts']['review']})")
    rv=g5.quarantine({"status":"reviewed","group":False})["rows"]
    check(any(x["like"]=="spam" and not x["label"] for x in rv) and not any("Hilltop" in x["sender"] for x in rv),"they are listed as like one you answered; other messages are untouched")
else:
    check(False,"expected several messages to review: "+str(q5["counts"]))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
