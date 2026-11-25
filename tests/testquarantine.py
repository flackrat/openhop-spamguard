# The quarantine list: every channel message with what SpamGuard did and why, in plain words; counts per
# status; copies grouped; filters for words, where it entered the mesh and who sent it; 1 or 7 days; and it
# needs the access key. All names and messages are made up.
import sys, json, logging, os, tempfile, time, threading, urllib.request, urllib.error
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time()
d=tempfile.mkdtemp(prefix="sg-q-")
rows=[]
for i in range(4): rows.append({"type":"msg","ts":now-600-i*20,"sender":f"RND{i}XQZ7","text":"FREE PRIZE claim now at spam.example/win","path":["C4","9D"],"channel":"Public","caught_by":"text:a","caught_kind":"text","caught_source":"dedupe","random":True})
for i in range(4): rows.append({"type":"msg","ts":now-5000-i*1500,"sender":"Bargain Barry","text":"Cheap radios at the car boot sale this Sunday, come early","path":["E1","9D"],"channel":"Public",
                                "caught_by":"slowrepeat:b" if i<2 else None,"caught_kind":"repeat" if i<2 else None,"caught_source":"slowrepeat" if i<2 else None})
rows.append({"type":"msg","ts":now-2400,"sender":"Trail Runner 7","text":"Anyone fancy a run up the ridge tomorrow?","path":["C4","2F"],"channel":"#trailchat","caught_by":"hop:C4","caught_kind":"hop","caught_source":"hop"})
rows.append({"type":"msg","ts":now-1900,"sender":"ZK4WQ0RT","text":"WIN WIN WIN reply YES now","path":["C4","9D"],"channel":"Public","random":True})
rows.append({"type":"msg","ts":now-900,"sender":"Hilltop Hiker","text":"Morning all, clear skies up here","path":["A7","2F"],"channel":"Public","known":True})
rows.append({"type":"msg","ts":now-800,"sender":"Repeater Bot","text":"our own repeater status","path":[],"channel":"Public","own":True})
rows.append({"type":"msg","ts":now-3*86400,"sender":"Canal Boat Ted","text":"Anyone hearing me from the lock?","path":["A7"],"channel":"Public","known":True})
with open(os.path.join(d,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh: fh.write("".join(json.dumps(r)+"\n" for r in rows if r["ts"]>now-86400))
with open(os.path.join(d,time.strftime("%Y-%m-%d",time.localtime(now-3*86400))+".jsonl"),"w") as fh: fh.write(json.dumps(rows[-1])+"\n")
m=mock(); g=guard(m, evidence_log=True, evidence_dir=d, listen_api_key="MADEUP-PAGE-KEY-0004")
r=g.quarantine({})
c=r["counts"]
check({k:c[k] for k in g.Q_STATUSES}=={"stopped":4+2,"held":1,"letthrough":1+2,"genuine":1} and c["review"]==1 and c["reviewed"]==0, f"each message gets one status: {c}")
g.cfg["review_missed"]=True; g._q_cache={}
check(g.quarantine({})["counts"]["review"]==4,"asked to, messages that went out are up for review too")
g.cfg["review_missed"]=False
check(g.quarantine({"status":"letthrough"})["counts"]["letthrough"]==3,"by default they are still listed under Missed spam")
check(r["source"]=="evidence" and r["days"]==1, "the last 24 hours, from the evidence log")
check(not any(x["sender"]=="Repeater Bot" for x in r["rows"]), "this repeater's own messages aren't listed")
byt={x["text"][:12]:x for x in r["rows"]}
fp=byt["FREE PRIZE c"]
check(fp["copies"]==4 and fp["senders"]==4 and fp["status"]=="stopped", "copies of one message are grouped, with how many names sent them")
check(fp["why"]=="A copy of a message already sent under another name", "and why, in plain words")
tr=[x for x in r["rows"] if x["sender"]=="Trail Runner 7"][0]
check(tr["status"]=="held" and "burst of made-up names" in tr["why"], "a normal name caught by a repeater block is held for review, not called spam")
bb=[x for x in r["rows"] if x["sender"]=="Bargain Barry"]
check({x["status"] for x in bb}=={"stopped","letthrough"}, "a repeating name's held copies are stopped, and the copies that went out first count as spam let through")
check(any("kept repeating" in x["why"] for x in bb), "with a reason saying so")
zk=[x for x in r["rows"] if x["sender"]=="ZK4WQ0RT"][0]
check(zk["status"]=="letthrough" and "made-up looking name" in zk["why"].lower(), "a made-up name that got through is spam let through")
r=g.quarantine({"group":False})
check(sum(1 for x in r["rows"] if x["text"].startswith("FREE"))==4, "copies can be shown one by one")
check(g.quarantine({"status":"held"})["rows"][0]["sender"]=="Trail Runner 7", "filtering by status")
check(g.quarantine({"status":"held"})["counts"]["stopped"]==6, "the counts stay for every status, so the filter buttons can show them")
check([x["sender"] for x in g.quarantine({"q":"ridge"})["rows"]]==["Trail Runner 7"], "searching words")
check(len(g.quarantine({"q":"barry"})["rows"])==2, "searching names")
rc=g.quarantine({"codes":["c4"]})
check({x["status"] for x in rc["rows"]} <= {"stopped","held","letthrough"} and rc["counts"]["genuine"]==0, "a map point's code lists the spam that entered there, not ordinary traffic")
check([x["sender"] for x in g.quarantine({"names":["Bargain Barry"],"group":False})["rows"]].count("Bargain Barry")==4, "a sender filter lists everything from them")
check(g.quarantine({"days":7})["counts"]["genuine"]==2, "the last 7 days")
try: g.quarantine({"status":"nonsense"}); check(False,"an unknown filter is refused")
except ValueError: check(True,"")
g.labels["p-none|x"]="spam"
# in memory, without the evidence log
m2=mock(); g2=guard(m2, floodguard=False)
m2.add("Hilltop Hiker","Morning all from the ridge",["A7","2F"])
g2.poll_once(); g2.poll_once()
r2=g2.quarantine({})
check(r2["source"]=="memory" and r2["rows"] and r2["rows"][0]["status"]=="genuine", "without the evidence log it lists what is still in memory")
# needs the key
srv=sg.QuietServer(("127.0.0.1",0),sg.make_handler(g)); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
def post(h):
    req=urllib.request.Request(f"http://127.0.0.1:{port}/quarantine",data=b'{}',method="POST",headers=h)
    try: return urllib.request.urlopen(req,timeout=10).status
    except urllib.error.HTTPError as e: return e.code
check(post({"Content-Type":"application/json"})==401, "the list needs the access key")
check(post({"Content-Type":"application/json","X-API-Key":"MADEUP-PAGE-KEY-0004"})==200, "and works with it")
srv.shutdown()
# --- 6.51: the review queue (made-up rows) ---
g9=guard(mock())
T=time.time()
def row(sender,text,**k):
    d={"ts":T-k.pop("ago",60),"packet":k.pop("packet",sender+text),"sender":sender,"text":text,"path":["A7"],"channel":"Public","random":False,"obfuscated":False,
       "known":False,"campaign_senders":0,"caught_by":None,"caught_kind":None,"caught_source":None,"own":False,"machine":None}
    d.update(k); return d
RAW=[row("Quarry Ann","Good morning all from the valley road",campaign_senders=3,ago=300),row("Quarry Bob","good morning all from the valley",campaign_senders=3,ago=200),
     row("Quarry Cy","Good morning all from the valley road, sunny here",campaign_senders=3,ago=100),
     row("QXZRT9","\x16\x1b garbled",random=True,garbage=True,ago=50),
     row("Quarry Dee","Free parts at qparts.example today only",campaign_senders=4,ago=40),
     row("Quarry Eve","Free parts at qparts.example today only, be quick",campaign_senders=4,ago=30),
     row("Quarry Fay","Selling spare radios at qradio.example",caught_by="b1",caught_kind=sorted(sg.PEOPLE_KINDS)[0],caught_source="burst",ago=20)]
g9._q_rows=lambda d:(RAW,"memory")
q=g9.quarantine({"status":"review","limit":100})
check(q["counts"]["review"]==2,"To review: the held message and the garbled one, not greetings that went out: %s"%q["counts"])
check(q["counts"]["letthrough"]>=5,"the rest are under Missed spam")
RAW.append(row("Q7XZPL","Cheap parts https://qparts.example/deal",random=True,campaign_senders=5,ago=10)); g9._q_cache={}
check(g9.quarantine({"status":"review","limit":100})["counts"]["review"]==3,"a link that went out from an unknown name stays in review")
q=g9.quarantine({"status":"letthrough","limit":100})
gm=[r for r in q["rows"] if "morning" in r["text"].lower()]
check(len({r["group"] for r in gm})==1 and gm[0]["group_size"]==len(gm)==3,"similar greetings form one group: %s"%[(r["text"],r["group"]) for r in gm])
idx=[i for i,r in enumerate(q["rows"]) if "morning" in r["text"].lower()]
check(idx==list(range(idx[0],idx[0]+3)),"a group's messages sit together")
check(q["groups"]<len(q["rows"]),"groups counted: %s groups, %s rows"%(q["groups"],len(q["rows"])))
# a reworded copy of a message you said was spam is matched, kept apart from your own answers
g9.labels={"Quarry DeeFree parts at qparts.example today only":"spam"}
q=g9.quarantine({"status":"all","limit":100})
check(q["counts"]["matched"]==1 and q["counts"]["reviewed"]==1,"SpamGuard's match isn't counted as your answer: %s"%q["counts"])
check([r["sender"] for r in g9.quarantine({"status":"matched"})["rows"]]==["Quarry Eve"],"the matched one is listed on its own")
# the count to review never shows a false zero
g9.labels={}; g9._review_count=(0,0); n=g9.to_review()
g9._review_count=(0,n); real=g9.quarantine
g9.quarantine=lambda b: (_ for _ in ()).throw(RuntimeError("made-up failure"))
check(g9.to_review()==n and g9._review_count_failed,"a failed count keeps the last number and says so")
g9.quarantine=real; g9._review_count=(0,n); g9.to_review()
check(not g9._review_count_failed,"and clears once it works")

# a Not spam answer covers that name only; a spam answer covers copies from any name
g8=guard(mock())
RAW8=[row("Quarry Gil","Morning from the ridge, all clear",caught_by="b2",caught_kind="hop",caught_source="burst",ago=90),
      row("Quarry Hal","Morning from the ridge, all clear",caught_by="b2",caught_kind="hop",caught_source="burst",ago=80)]
g8._q_rows=lambda d:(RAW8,"memory")
check(g8.quarantine({"status":"review"})["counts"]["review"]==2,"two names, the same held text: both to review")
g8.labels={"Quarry GilMorning from the ridge, all clear":"not_spam"}
q=g8.quarantine({"status":"review"})
check(q["counts"]["review"]==1 and q["rows"][0]["sender"]=="Quarry Hal","Not spam for one name leaves the other name's copy to review")
g8.labels={"Quarry GilMorning from the ridge, all clear":"spam"}
check(g8.quarantine({"status":"review"})["counts"]["review"]==0,"Spam for one covers the copies from every name")

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
