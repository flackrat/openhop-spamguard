# 6.56.0: four experimental settings, all off by default, and two display changes.
# Punctuation names count as made up; new arrivals on a familiar way in stay off Missed spam; replay watch flags old
# packets heard again (flags only); a hold still catching is renewed; lookalike names can be watched in one go;
# Bot-safe channels keep their copied greetings off Missed spam; FloodGuard's own drops say so. Made-up names only.
import sys, os, time, json, struct, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

for k in ("punct_names","newcomer_quiet","replay_watch","renew_holds"):
    check(sg.DEFAULT_CONFIG.get(k) is False,"%s is off by default"%k)
    meta=[d for d in sg.SETTINGS_META if d["key"]==k]
    check(meta and meta[0]["group"]=="Experimental","%s is listed under Experimental"%k)

# --- punctuation names
for n in ("Q*9XC1DT","(QZ7BJW3","2>Q-QSGL"):
    check(sg.name_score(n,[],True)>=4 and sg.name_score(n,[])<4,"%s counts as made up only when the setting is on"%n)
for n in ("Q1QQQ-V4","Q4ABC/P","QUARRY12","Quarry (Mob)","Q*9XC1DT🔥"):
    check(sg.name_score(n,[],True)==sg.name_score(n,[]),"%s is left alone"%n)

# --- new arrivals on a familiar way in, and Bot-safe channels, off Missed spam
m=mock(); g=guard(m); g.poll_once()
row={"sender":"QX7QA2B9","text":"Good morning all","random":True,"known":False,"channel":"Public","way_known":2,"new_via":1}
check(g._q_classify(row)[0]=="letthrough","off: a made-up looking newcomer is listed under Missed spam")
g.apply_settings({"newcomer_quiet":True})
check(g._q_classify(row)[0]=="genuine","on: a newcomer on a familiar way in is passed as normal")
check(g._q_classify(dict(row,new_via=3))[0]=="letthrough","not when several new names came in that way in the hour")
check(g._q_classify(dict(row,way_known=0))[0]=="letthrough","not on a way nobody known uses")
check(g._q_classify(dict(row,text="quarry-example.co.uk is the real site"))[0]=="letthrough","not with a web address")
check(g._q_classify(dict(row,obfuscated=True))[0]=="letthrough","not with hidden characters in the name")
check(g._q_classify(dict(row,caught_by="x",caught_kind="text",caught_source="campaign"))[0]=="stopped","holds are untouched")
g.apply_settings({"newcomer_quiet":False}); g.botsafe_channels.add("#quarrytest")
check(g._q_classify(dict(row,channel="#quarrytest",way_known=0))[0]=="genuine","Bot-safe channel: copied greetings aren't listed as missed spam")

# the way in is learned as messages arrive
m=mock(); g=guard(m); g.poll_once()
for n in ("Quarry Ann","Quarry Bob"):
    g.known[n]=[time.time()-86400,time.time()-3600,5]
    m.add(n,"hello from the quarry",["A1","B2"],ago=30)
g.poll_once()
m.add("QNEW1X9Z","anyone about?",["A1","C3"]); g.poll_once()
e=[x for x in g.events if x.sender=="QNEW1X9Z"][0]
check(e.way_known==2 and e.new_via==1,"a new name on a way two known names used: %s %s"%(e.way_known,e.new_via))
for i in range(3): m.add("QBURST%d9"%i,"anyone about?",["A1","D4"])
g.poll_once()
e=[x for x in g.events if x.sender=="QBURST29"][0]
check(e.new_via>=4,"a burst of new names that way is counted: %s"%e.new_via)
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check("A1" in g2.way_names,"the familiar ways in survive a restart")

# --- renew a hold that is still catching
m=mock(); g=guard(m); g.poll_once()
now=time.time()
def hold(key,last_spam,made):
    g.blocks[key]={"kind":"repeat","value":"Quarry slogan","source":"slowrepeat","created":made,"expires":now-1,"hits":40,"last_spam":last_spam}
hold("r1",now-3*3600,now-86400*2); g._expire_blocks(now)
check("r1" not in g.blocks,"off: a hold ends when its time is up")
g.apply_settings({"renew_holds":True})
hold("r1",now-3*3600,now-86400*2); g._expire_blocks(now)
check("r1" in g.blocks and g.blocks["r1"]["expires"]>now and g.blocks["r1"]["renewed"]==1,"on: still catching in the last few hours, so renewed")
check(g.blocks["r1"]["expires"]-now<=12*3600+5,"for half a day at most")
hold("r2",now-8*3600,now-86400); g._expire_blocks(now); check("r2" not in g.blocks,"a hold gone quiet still ends")
hold("r3",now-600,now-8*86400); g._expire_blocks(now); check("r3" not in g.blocks,"never more than a week from when it was made")
check(any("still catching spam, so it was renewed" in a["msg"] for a in g.activity),"Activity says so")

# --- lookalike names
m=mock(); g=guard(m); g.poll_once()
for n in ("Quarry Q is a fraudster 🦊","Quarry Q is*a fraudster 🦊","-Quarry Q is a fraud 🦊","Quarry Bob","Quarry Ann"):
    g.known[n]=[time.time()-600,time.time()-60,3]
r=g.action("watch",{"name":"Quarry Q is a fraudster 🦊","on":True})
check("2 names like it" in r.get("message",""),"putting one on watch mentions its lookalikes: %s"%r.get("message"))
rows=g.people({"show":"watch"})["rows"]
check(rows and sorted(rows[0]["lookalikes"])==sorted(["Quarry Q is*a fraudster 🦊","-Quarry Q is a fraud 🦊"]),"its row offers them: %s"%(rows and rows[0].get("lookalikes")))
g.action("watch_many",{"names":rows[0]["lookalikes"]})
check(all(n in g.on_watch for n in rows[0]["lookalikes"]) and "Quarry Bob" not in g.on_watch,"one tap watches them all, nobody else")
check(g.people({"show":"watch"})["rows"][0]["lookalikes"]==[],"and they aren't offered again")

# --- replay watch
m=mock(); g=guard(m); g.poll_once()
h=os.urandom(8).hex(); t0=time.time()-3600
m.packets.append({"id":900,"timestamp":t0,"type":5,"payload":enc("Quarry Ann","meet at the quarry gate"),"packet_hash":h,"original_path":json.dumps(["A1","B2"]),"is_duplicate":False})
g.poll_once()
m.packets.append({"id":901,"timestamp":time.time(),"type":5,"payload":m.packets[-1]["payload"],"packet_hash":h,"original_path":json.dumps(["C3"]),"is_duplicate":False})
g.poll_once()
check(not g.rw_flags and g.status().get("replay_watch") is None,"off: nothing is flagged")
m=mock(); g=guard(m,replay_watch=True); g.poll_once()
m.packets.append({"id":900,"timestamp":t0,"type":5,"payload":enc("Quarry Ann","meet at the quarry gate"),"packet_hash":h,"original_path":json.dumps(["A1","B2"]),"is_duplicate":False})
g.poll_once()
m.packets.append({"id":901,"timestamp":t0+20,"type":5,"payload":m.packets[-1]["payload"],"packet_hash":h,"original_path":json.dumps(["D4"]),"is_duplicate":True})
g.poll_once(); check(not g.rw_flags,"an ordinary echo moments later isn't flagged")
m.packets.append({"id":902,"timestamp":time.time(),"type":5,"payload":m.packets[-1]["payload"],"packet_hash":h,"original_path":json.dumps(["C3"]),"is_duplicate":False})
g.poll_once()
check(len(g.rw_flags)==1 and g.rw_flags[0]["kind"]=="packet" and g.rw_flags[0]["sender"]=="Quarry Ann" and g.rw_flags[0]["gap"]>=3500,"the same packet an hour later is flagged: %s"%list(g.rw_flags))
check(not g.blocks or not any(b.get("source")=="replay" for b in g.blocks.values()),"nothing is held for it")
st=g.status()["replay_watch"]; check(st["packet"]==1 and st["days"][-1]==1 and st["latest"][0]["sender"]=="Quarry Ann","Overview counts it: %s"%st)
q=g.quarantine({"status":"all","days":1}); rr=[r for r in q["rows"] if r["packet"]==h]
check(rr and rr[0]["replay_watch"] and rr[0]["replay_watch"]["kind"]=="packet","Messages tags the message")
g.poll_once(); check(len(g.rw_flags)==1,"flagged once")
# adverts: an older one played back after a newer one
def advert(t,name="Quarry Hill Rpt",key=b"\x5a"*32):
    return (key+struct.pack("<I",int(t))+bytes(64)+bytes([2|0x80])+name.encode()).hex()
m.packets.append({"id":903,"timestamp":time.time(),"type":sg.PAYLOAD_TYPE_ADVERT,"payload":advert(time.time()),"packet_hash":os.urandom(8).hex(),"original_path":"[]"})
g.poll_once()
m.packets.append({"id":904,"timestamp":time.time()+1,"type":sg.PAYLOAD_TYPE_ADVERT,"payload":advert(time.time()-86400),"packet_hash":os.urandom(8).hex(),"original_path":json.dumps(["E5"])})
g.poll_once()
check(g.status()["replay_watch"]["advert"]==1,"an advert older than one already heard is flagged: %s"%list(g.rw_flags))
g._rw_save(); g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg)); g2._rw_load()
check(len(g2.rw_seen)==len(g.rw_seen) and len(g2.rw_flags)==len(g.rw_flags),"the packet memory and flags survive a restart")
check(os.path.getsize(g._rw_file())==10*len(g.rw_seen),"ten bytes per packet remembered")

# --- FloodGuard's own drops say so
m=mock(); g=guard(m); g.poll_once()
g.rule_ids["flood:limit"]=4242
h2=os.urandom(8).hex()
m.packets.append({"id":950,"timestamp":time.time(),"type":5,"payload":enc("Quarry Far","rx 24 hops"),"packet_hash":h2,"original_path":json.dumps(["F6"]),"transmitted":False,"drop_reason":"Policy blocked packet (rule 4242)"})
g.poll_once()
q=g.quarantine({"status":"all","days":1}); rr=[r for r in q["rows"] if r["packet"]==h2]
check(rr and rr[0]["not_passed"]=="floodguard","a message FloodGuard didn't pass on says so: %s"%(rr and rr[0].get("not_passed")))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
