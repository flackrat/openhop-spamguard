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
check(c=={"stopped":4+2,"held":1,"letthrough":1+2,"genuine":1}, f"each message gets one status: {c}")
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
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
