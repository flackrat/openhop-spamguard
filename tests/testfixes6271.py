# 6.27.1 fixes. In Monitor your own drop rules win over SpamGuard's record-only rules; a regular who keeps
# chatting stays known past 24 hours; campaigns from keyboard-noise names count as made-up; a known name
# repeating itself is never held by the double-send hold; the advisor counts reworded-spam holds.
# All names and messages are made up.
import sys, os, time, json, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
SPAM="Join the big giveaway at examplespam dot site now"

# 1. Monitor: the owner's drop comes first and wins; Protect keeps SpamGuard first
m=mock(); g=guard(m, floodguard=False, auto_protect=False)
m.policy["policy_engine"]["rules"]=[{"id":1,"name":"my own rule","enabled":True,"if":{"field":"hop_count","op":"gte","value":2},"then":{"action":"drop"}}]
g.apply_settings({"mode":"monitor"})
for i in range(5): m.add(rname(),SPAM,["9D","4C"],ago=100-i*5)
sync(g)
rules=m.policy["policy_engine"]["rules"]
ours=[r for r in rules if str(r.get("name","")).startswith("spamguard:")]
check(ours and not any(r["then"]["action"]=="drop" for r in ours),"monitor: SpamGuard drops nothing")
check(rules[0]["name"]=="my own rule","monitor: your rule is first")
check(m.decide("Someone",SPAM,["9D","4C"])=="drop","monitor: your drop still drops the campaign text")
check(g.status().get("rules",{}).get("after_yours", g.rule_summary["after_yours"]) is True,"monitor: the rules page says SpamGuard's rules come after yours")
g.apply_settings({"mode":"protect"}); g.last_sync=0; g.sync_pending=True; g.poll_once()
rules=m.policy["policy_engine"]["rules"]
check(str(rules[0]["name"]).startswith("spamguard:") and g.rule_summary["after_yours"] is False,"protect: SpamGuard's rules come first again")
check(m.decide("Someone",SPAM,["9D","4C"])=="drop","protect: still dropped")

# 2. Sender history is kept a day from when the name was LAST heard
m=mock(); g=guard(m, floodguard=False)
now=time.time()
g.sender_history["Hilltop Hiker"]={"first":now-30*3600,"count":40,"last":now-600,"hops":set()}
g.sender_history["Gone Quiet"]={"first":now-30*3600,"count":5,"last":now-25*3600,"hops":set()}
m.add("Bystander","hello",["4C"],ago=5); g.poll_once()
check("Hilltop Hiker" in g.sender_history,"a regular first heard 30 hours ago but heard 10 minutes ago is kept")
check("Gone Quiet" not in g.sender_history,"a name not heard for 25 hours is forgotten")
m.add("Hilltop Hiker","morning all",["4C"],ago=1); g.poll_once()
check(g.sender_history["Hilltop Hiker"]["last"]>now-60,"hearing them again moves 'last' on")
g._save_state(force=True)
st=json.load(open(g.file_cfg.get("state_file")))
check(len(st["senders"]["Hilltop Hiker"])==3,"the state file keeps first, count and last")
g2=sg.SpamGuard(dict(g.file_cfg)); check("Hilltop Hiker" in g2.sender_history and g2.sender_history["Hilltop Hiker"]["count"]>=40,"reloads with last")
st["senders"]={"Old Format":[now-3600,3]}; json.dump(st,open(g.file_cfg.get("state_file"),"w"))
g3=sg.SpamGuard(dict(g.file_cfg)); check("Old Format" in g3.sender_history,"an older state file without last still loads")

# 3. Keyboard-noise names
check(all(sg.noise_name(n) for n in ("Q,ZWX*%B","(£TT4(K<","=M$9YRL-")),"keyboard-noise names spotted")
check(not any(sg.noise_name(n) for n in ("GRUB#2","MOKKA-P7","G9XYZ/P1","BOT-01-X","Dave M","Hilltop Hiker","UXQWYXQQ","N0CALL")),"ordinary, callsign and short names are not")
m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i,n in enumerate(("Q,ZWX*%B","(£TT4(K<","=M$9YRL-")): m.add(n,"Cheap watches and free prizes waiting for you on my page tonight",["9D","4C"],ago=60-i*5)
sync(g)
cc=[c for c in g.clusters.values() if len(c["senders"])>=2]
check(cc and any(c.get("strong") for c in cc),"a campaign from keyboard-noise names is strong")
hop_noise={k for k,b in g.blocks.items() if b.get("source")=="hop"}
m2=mock(); g2=guard(m2, floodguard=False); g2.apply_settings({"mode":"protect"})
for i,n in enumerate(("Rambler One","Rambler Two","Rambler Six")): m2.add(n,"Cheap watches and free prizes waiting for you on my page tonight",["9D","4C"],ago=60-i*5)
sync(g2)
check(hop_noise=={k for k,b in g2.blocks.items() if b.get("source")=="hop"},"noise names don't make repeater blocks any more likely than ordinary new names")
check(not any(c.get("strong") for c in g2.clusters.values()),"the same campaign from ordinary new names is not strong")

# 4. Double-send hold never holds a known name; a new name still is
for known,label in ((True,"known"),(False,"new")):
    m=mock(); g=guard(m, floodguard=False, quick_resend_hold=True, known_min_msgs=1); g.apply_settings({"mode":"protect"})
    who="Regular Rita" if known else "Stranger Sam"
    if known:
        g.known[who]=[time.time()-5*86400, 50, time.time()-60]
    for i in range(3): m.add(who,"Can anyone hear me on this channel tonight",["4C"],ago=40-i*12)
    sync(g)
    held=any(str(k).startswith("resend:") for k in g.blocks)
    check(g.stats["resends"]>=1,f"{label}: the double send is counted")
    check(held is (not known),f"{label}: {'not held' if known else 'held'}")

# 5. Advisor counts reworded-spam holds
m=mock(); g=guard(m, floodguard=False, text_sense=True, text_sense_log_only=False)
g._hist_bump(time.time()-60,"sh"); g._hist_bump(time.time()-120,"sh")
f=[x for x in g.advisor()["families"] if x["key"]=="text_sense"][0]
check("Held 2 times" in f["status"],"advisor shows reworded-spam holds: "+f["status"])
check(g.experiments_summary()["sense_held_3d"]==2,"evidence summary carries them")
print("testfixes6271: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
