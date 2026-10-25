# The spam map: a repeat spammer is shown as one sender, placed from the repeaters that hear them first, even
# when much of what they send gets through; circles can be sized by senders as well as messages; and the spam
# behind a point can be listed. Nothing here blocks anyone. All names, messages and places are made up.
import sys, json, logging, os, tempfile, time, threading, urllib.request, urllib.error
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

# --- who is a repeat spammer, and what is remembered about them
m=mock(); g=guard(m, repeat_max=3, floodguard=False)
# copies of one message already held earlier today (messages are counted two minutes after they arrive)
today=str(int(time.mktime(time.localtime()[:3]+(0,0,0,0,0,-1))))
g.held_names["Bargain Barry"]={today:[6,3]}
m.add("Bargain Barry","Anyone selling a spare antenna mast?",["E1","9D"],ago=400)
m.add("Bargain Barry","Morning all from the market, lovely day",["7B","A7"],ago=350)
for i in range(4):
    m.add("Hilltop Hiker",f"Lovely views from the top today, number {i}",["A7","2F"],ago=500-i*60)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(g.repeat_spammer("Bargain Barry"), "a name with repeated copies held counts as a repeat spammer")
check(not g.repeat_spammer("Hilltop Hiker"), "someone chatting normally doesn't")
sp=g.sender_paths.get("Bargain Barry") or {}
firsts={k.split(">")[0] for k in sp}
check({"E1","7B"} <= firsts, f"their other messages are remembered too, to show where they are heard from: {sorted(firsts)}")
check("Hilltop Hiker" not in g.sender_paths, "nothing is remembered about people who aren't repeat spammers")
check(all(len(k.split(">"))<=g.SENDER_PATH_HOPS for k in sp), "only the start of each route is kept")
# survives a restart
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.sender_paths.get("Bargain Barry")==sp, "what's remembered survives a restart")

# --- one sender, placed from several repeaters (locations made up, around an invented town)
LOC={"C4":(51.50,-0.90,"Ridge Relay"),"E1":(51.56,-0.82,"Mill Hill Rpt"),"7B":(51.46,-0.80,"Canal Node")}
def fake_resolve(path, distrust=frozenset()):
    c=path[0]
    if c not in LOC: return None
    lat,lon,name=LOC[c]
    return {"kind":"id","key":c*8,"name":name,"lat":lat,"lon":lon,"code":c,"sure":True,"index":0}
g.resolve_path=fake_resolve
day=str(int(time.mktime(time.localtime()[:3]+(0,0,0,0,0,-1))))
spammers={"Fox One":{"C4>9D":{day:8},"E1>9D":{day:5}},"Fox Two":{"7B>A7":{day:4}},"Lonely":{"ZZ>01":{day:9}},"Quiet":{"C4>9D":{day:1}}}
links={"Fox Two":["Fox One"]}
now=time.time()
snd,unpl=g.spam_senders(spammers,links,now-86400,now-7*86400)
fox=[x for x in snd if "Fox One" in x["names"]]
check(len(fox)==1 and set(fox[0]["names"])=={"Fox One","Fox Two"}, f"names that carried on each other's count are one sender: {[x['names'] for x in snd]}")
if fox:
    f=fox[0]
    check(f["d7"]==17 and len(f["repeaters"])==3, f"every message counts, and all three repeaters that heard them first: {f['d7']} {len(f['repeaters'])}")
    check(51.45<f["lat"]<51.57 and -0.91<f["lon"]<-0.79, "the area sits among those repeaters")
    check(3<=f["radius_km"]<=g.AREA_KM, f"with a sensible radius: {f['radius_km']}")
    check(f["repeaters"][0]["code"]=="C4", "the repeater that hears them most comes first")
check(unpl==1, "a sender whose repeaters can't be placed is counted as unplaced, not drawn")
check(not any("Quiet" in x["names"] for x in snd), "a name heard too few times isn't drawn")

# --- circles sized by senders: who sent the spam, counted without keeping names
g.resolve_path=fake_resolve
g._learned_table={}
hour=str(int(now//3600*3600))
hist={hour:{"p":{"C4>9D":5,"E1>9D":2},"s":{"C4>9D":["a1b2c3","d4e5f6"],"E1>9D":["a1b2c3"]}}}
ent=g.spam_entries(now-86400,now-7*86400,hist)
byc={e["code"]:e for e in ent["entries"]}
check(byc.get("C4",{}).get("s7")==2 and byc.get("C4",{}).get("d7")==5, f"a circle knows how many senders as well as messages: {byc.get('C4')}")
old={hour:{"p":{"C4>9D":5}}}
check(g.spam_entries(now-86400,now-7*86400,old)["entries"][0]["s7"] is None, "spam from before senders were counted says so, rather than claiming one")
check("senders" in ent and "senders_unplaced" in ent, "the map is told about repeat spammers")
# no names in the counts
m3=mock(); g3=guard(m3, floodguard=False)
for i in range(5): m3.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D"],ago=300-i)
g3.poll_once(); g3.poll_once()
blob=json.dumps(g3.hist)
check('"s"' in blob and not any(e.sender in blob for e in g3.events), "senders are counted by a short code, never by name")

# --- the spam behind a point, from the evidence log
d=tempfile.mkdtemp(prefix="sg-msgs-")
m4=mock(); g4=guard(m4, evidence_log=True, evidence_dir=d, listen_api_key="MADEUP-PAGE-KEY-0003")
rows=[{"type":"msg","ts":now-3600,"sender":"UD6DWREK","text":"FREE PRIZE claim now","path":["C4","9D"],"channel":"Public","caught_by":"text:1"},
      {"type":"msg","ts":now-3000,"sender":"Hilltop Hiker","text":"Morning all","path":["C4","2F"],"channel":"Public"},
      {"type":"msg","ts":now-2000,"sender":"Fox One","text":"Morning from the market","path":["E1","9D"],"channel":"Public"},
      {"type":"msg","ts":now-9*86400,"sender":"UD6DWREK","text":"too old","path":["C4"],"channel":"Public","caught_by":"text:1"}]
with open(os.path.join(d,time.strftime("%Y-%m-%d")+".jsonl"),"w") as fh:
    fh.write("".join(json.dumps(r)+"\n" for r in rows))
r=g4.messages_for({"codes":["c4"]})
check(r["source"]=="evidence" and [x["sender"] for x in r["messages"]]==["UD6DWREK"], f"spam that entered through a code, and not ordinary messages that took the same route: {r}")
r=g4.messages_for({"names":["Fox One"]})
check([x["text"] for x in r["messages"]]==["Morning from the market"], "every message from a repeat spammer, to show where they're heard from")
try: g4.messages_for({}); check(False,"asking for nothing is refused")
except ValueError: check(True,"")
srv=sg.QuietServer(("127.0.0.1",0),sg.make_handler(g4)); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
def post(h):
    req=urllib.request.Request(f"http://127.0.0.1:{port}/messages_for",data=b'{"codes":["C4"]}',method="POST",headers=h)
    try: return urllib.request.urlopen(req,timeout=10).status
    except urllib.error.HTTPError as e: return e.code
check(post({"Content-Type":"application/json"})==401, "listing messages needs the access key, like the evidence log")
check(post({"Content-Type":"application/json","X-API-Key":"MADEUP-PAGE-KEY-0003"})==200, "and works with it")
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
