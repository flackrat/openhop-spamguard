# Points from the 6.52 review: bot channels by whole words only; sender codes that can't be matched across channels
# or days and are deleted after the day; "Protected" only with recently confirmed rules; your own openHop rules and
# objects untouched by channel mode changes; the newest save by its number; where setting changes came from;
# channels SpamGuard reads listed before their first message. Made-up names and messages only.
import sys, os, time, json, gzip, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
# --- bot channel names: whole words only
g=guard(mock())
for n in ("#latest","#contest","#botany","#newspaper","#pinging","#testament","#alertness","#Public2"):
    check(g.bot_channel(n) is None,"an ordinary channel isn't taken for a bot channel: %s"%n)
for n in ("#test","#weather","#weather-alerts","#bot_status","#uk-wx","#test2","#ping","#news","#wardriving","#bots"):
    check(g.bot_channel(n),"a bot channel is recognised: %s"%n)
check("'weather'" in g.bot_channel("#weather-alerts"),"and it says which word: %s"%g.bot_channel("#weather-alerts"))
r=g.action("add_channel",{"name":"#latest","key":""})
check("#latest" not in g.botsafe_channels,"adding #latest keeps full protection")
r=g.action("add_channel",{"name":"#weather","key":""})
check("#weather" in g.botsafe_channels and "'weather'" in r["message"] and "Block spam" in r["message"],"adding #weather says why it's bot-safe and how to change it: %s"%r["message"])
# --- sender codes
now=time.time(); pub=g.cfg["channels"]["Public"]; qc=sg.hashtag_secret("#quarrychat")
def note(secret,sender,day_ts):
    p=bytes.fromhex(enc(sender,"hello",key=secret))
    g._chan_note(p, sg.decrypt_group_text(p,{"Public":pub} if secret==pub else {"#quarrychat":qc}), day_ts)
g.cfg["channels"]["#quarrychat"]=qc
note(pub,"Quarry Ann",now); note(qc,"Quarry Ann",now)
day=time.strftime("%Y-%m-%d",time.localtime(now))
a=g.chan_heard["n:Public"]["days"][day][2]; b=g.chan_heard["n:#quarrychat"]["days"][day][2]
check(a and b and set(a).isdisjoint(b),"the same name gets different codes on different channels")
key1=g.chan_key["key"]; codes_today=list(a)
g._save_state(force=True); raw=gzip.decompress(open(g.cfg["state_file"]+".gz","rb").read()).decode()
check("Quarry Ann" not in raw.split('"chan_heard"')[1][:5000] if '"chan_heard"' in raw else True,"no sender name kept in the channel counts")
tomorrow=now+86400; note(pub,"Quarry Ann",tomorrow)
day2=time.strftime("%Y-%m-%d",time.localtime(tomorrow))
check(g.chan_key["key"]!=key1 and g.chan_key["day"]==day2,"a new key each day")
check(g.chan_heard["n:Public"]["days"][day][2]==[] and g.chan_heard["n:Public"]["days"][day][1]==1,"yesterday keeps its count, its codes are deleted")
check(set(g.chan_heard["n:Public"]["days"][day2][2]).isdisjoint(codes_today),"the same name gets a different code the next day")
# --- protection only with recently confirmed rules
m=mock(); g2=guard(m); g2.apply_settings({"mode":"protect"}); g2.poll_once(); g2.last_sync=0; g2.sync_pending=True; g2.poll_once(); g2.loop_beat=time.time()
check(g2.protection()["state"]=="ok","rules just confirmed: protected")
g2.rules_confirmed=time.time()-3600; p=g2.protection(); rp=next(x for x in p["parts"] if x["part"]=="rules")
check(p["state"]=="partly" and "confirmed" in p["line"] and rp["state"]=="warn","rules not confirmed for an hour: not shown as fully protected: %s"%p["line"])
g2.rules_checked=time.time(); check(g2.protection()["state"]=="partly","reading the rules alone doesn't count as confirming them")
g2.sync_policy(); check(g2.protection()["state"]=="ok" and time.time()-g2.rules_confirmed<5,"a read that finds them all in place confirms them again")
f={x["part"]:x for x in g2.health()["fresh"]}; check(f["rules"]["label"].startswith("Rules confirmed"),"Health shows when rules were last confirmed")
# --- channel modes never touch your own rules or other openHop objects
m.policy["policy_engine"]["objects"]["my_list"]={"names":["Quarry Own"]}
g2.action("add_channel",{"name":"#quarryweather","key":""}); g2.sync_policy(force=True)
before=[r for r in m.policy["policy_engine"]["rules"] if r.get("id")==1]
for mode in ("full","watch","botsafe","full"):
    g2.action("channel_blocking",{"name":"#quarryweather","mode":mode,"confirm":True}); g2.sync_policy(force=True)
    pe=m.policy["policy_engine"]
    check([r for r in pe["rules"] if r.get("id")==1]==before and pe["objects"].get("my_list")=={"names":["Quarry Own"]},
          "switching a channel to %s leaves your own rule and objects alone"%mode)
# --- the newest save by its number
g3=guard(mock()); g3.blocks.append({"id":"x1","type":"text","value":"quarry save one","by":"you","ts":time.time()}) if isinstance(g3.blocks,list) else None
g3._save_state(force=True); g3._save_state(force=True)
path=g3.cfg["state_file"]
s_new=sg.read_state_file(path+".gz")["save_seq"]; s_old=sg.read_state_file(path+".gz.bak")["save_seq"]
check(s_new==s_old+1,"each save has the next number")
past=time.time()-3600; os.utime(path+".gz",(past,past))   # a copy or restore changed the date of the newest
check(sg.state_order(path)[0]==path+".gz","the newest save wins by its number, whatever the dates say")
raw=gzip.decompress(open(path+".gz.bak","rb").read()); st=json.loads(raw); st.pop("save_seq",None)
open(path+".gz.bak","wb").write(gzip.compress(json.dumps(st).encode())); os.utime(path+".gz.bak",None)
check(sg.state_order(path)[0]==path+".gz.bak","a newest file without a number (an older version after a rollback) keeps its place")
# --- where setting changes came from
m4=mock(); g4=guard(m4); g4.apply_settings({"level":60}); g4._save_state(force=True)
fc=dict(g4.file_cfg); g5=sg.SpamGuard(fc)
check(len(g5.settings_history)==len(g4.settings_history),"a restart with nothing changed records nothing")
g5.settings["level"]=75; g5._save_state(force=True)   # as if changed outside the page before the next start
st=sg.read_state_file(g5.cfg["state_file"]+".gz"); st["hist_last"]["level"]=60
open(g5.cfg["state_file"]+".gz","wb").write(gzip.compress(json.dumps(st).encode()))
g6=sg.SpamGuard(fc)
check(g6.settings_history and g6.settings_history[0]["by"].startswith("At start-up") and g6.settings_history[0]["new"].startswith("75"),
      "a change found at start-up says so: %s"%(list(g6.settings_history)[:1],))
g6.action("profile_save",{"name":"Quarry calm"}); g6.apply_settings({"level":30})
g6.action("profile_apply",{"name":"Quarry calm"})
check(g6.settings_history[0]["by"]=="Profile 'Quarry calm'","a profile says it made the change: %s"%g6.settings_history[0]["by"])
# --- channels SpamGuard reads are listed before their first message
g7=guard(mock()); g7.action("add_channel",{"name":"#quarryquiet","key":""}); g7._chh_cache=None
rows={r["name"]:r for r in g7.channels_heard(time.time())}
check("#quarryquiet" in rows and rows["#quarryquiet"]["kind"]=="read" and rows["#quarryquiet"]["d30"]==0,"a read channel with no messages yet is listed")
# --- why it got through: settings as they were then
m8=mock(); g8=guard(m8); g8.apply_settings({"mode":"monitor"}); g8.poll_once()
m8.add("Quarry Newcomer","Win a free radio, reply now please",["A1","B2"],ago=5); g8.poll_once()
e=[x for x in g8.events if x.sender=="Quarry Newcomer"][0]
check(e.mode_then=="monitor","the mode is kept with each message")
g8.apply_settings({"mode":"protect"}); e.matched="text:x"
check("Monitor only" in (g8.why_through({"packet":e.packet}) or ""),"Monitor then is the reason, even after switching to Protect")
e.matched=None; w=g8.why_through({"packet":e.packet})
check(w.startswith("It probably got through"),"a reason worked out from history says probably: %s"%w)
# --- diagnostic export: nothing that identifies the mesh or its people
m9=mock(); g9=guard(m9)
for i in range(6): m9.add(f"Quarry Secret{i}",f"Private plan number {i} at the old quarry",["A1","B2"],ago=60-i)
g9.poll_once(); g9.action("add_channel",{"name":"#quarryhidden","key":""})
g9.apply_settings({"level":62})
d=g9.diagnostics(); txt=json.dumps(d)
for bad in ["Quarry Secret","Private plan","#quarryhidden",sg.hashtag_secret("#quarryhidden"),g9.cfg["channels"]["Public"],"A1","B2"]:
    check(bad not in txt,"the export leaves out %r"%bad)
check(d["spamguard"]==sg.VERSION and d["level"]==62 and len(d["settings"])>20 and d["counts"]["channels_read"]>=2,"and keeps versions, settings and counts")
check(d["settings_changes"] and d["settings_changes"][0]["by"],"with recent setting changes")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
