# Trust from a not-spam mark covers that channel only; a spam mark on a trusted name withdraws trust; People shows
# your marks, disagreements and how close a new name is to being known; "new place" warnings are rate-limited.
# Checked against openHop's own rule engine. All names, channels and messages are made up.
import sys, logging, time, json, os
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g._urgent_sync=True; g.poll_once()
NEWS=sg.hashtag_secret("#widgetnews")
m=mock(); g=guard(m, floodguard=False, known_min_msgs=3, known_min_minutes=60)
g.apply_settings({"mode":"protect"}); g.action("add_channel",{"name":"#widgetnews"})
check("#widgetnews" in g.botsafe_channels,"a news channel gets bot-safe protection")
g.action("channel_blocking",{"name":"#widgetnews","mode":"full","confirm":True}); sync(g)   # you said yes, full blocking there
check("#widgetnews" in g.cfg["channels"],"a second channel is read")
# a hold that stops unknown names everywhere (a lockdown), so trust is what lets someone through
g._add_block("lockdown","lockdown",None,"made up","manual",ttl=3600); sync(g)
m.add("Bot Seven","Headlines at eleven",["4C"],key=NEWS,ago=300); sync(g)
check(m.decide("Bot Seven","Headlines at noon",["4C"],key=NEWS)=="drop","before: an unknown name is held on the news channel")
# not spam on a held message on the news channel: trusted there only
r=g.give_verdict({"verdict":"not_spam","status":"held","sender":"Bot Seven","text":"Headlines at noon","path":["4C"],
                   "packet":"pk1","channel":"#widgetnews","matched":"lockdown"})
sync(g)
check("Bot Seven" not in g.allow_senders and "#widgetnews" in g.trust_on.get("Bot Seven",{}),"trusted on that channel, not everywhere")
check("on #widgetnews" in r["message"],"the answer says where: "+r["message"])
check(m.decide("Bot Seven","Headlines at one",["4C"],key=NEWS)=="allow","passes on that channel")
check(m.decide("Bot Seven","Headlines at one",["4C"])=="drop","still held on Public, where anyone could type the name")
check(any(r2["name"].startswith("spamguard:trusted-on:") for r2 in m.policy["policy_engine"]["rules"]),"one allow rule for the channel")
e=sg.Event(ts=time.time(),sender="Bot Seven",text="Headlines at two",path=["4C"],channel="#widgetnews")
check(g.trusted_here("Bot Seven","#widgetnews") and not g.trusted_here("Bot Seven","Public"),"SpamGuard's own checks see the same")
# People shows it
row=lambda n: next(x for x in g.people({"show":"all","q":n})["rows"] if x["name"]==n)
p=row("Bot Seven")
check(p["trusted_on"]==["#widgetnews"] and not p["trusted"],"People: trusted on the channel")
check(p["marks"] and p["marks"]["genuine"]==1 and not p["marks"]["mixed"],"People: your marks are counted")
# a spam mark withdraws trust, and People flags the disagreement
r=g.give_verdict({"verdict":"spam","status":"letthrough","sender":"Bot Seven","text":"cheap widgets click here now","path":["4C"],
                   "packet":"pk2","channel":"#widgetnews"})
sync(g)
check("Bot Seven" not in g.trust_on and "no longer trusted" in r["message"],"a spam mark withdraws trust: "+r["message"])
check(m.decide("Bot Seven","Headlines at three",["4C"],key=NEWS)=="drop","held again on the channel")
check(row("Bot Seven")["marks"]["mixed"],"People flags marks that disagree")
# a globally trusted name marked spam loses trust too
g.action("allow_sender",{"sender":"Pat Copy"})
g.give_verdict({"verdict":"spam","status":"letthrough","sender":"Pat Copy","text":"free gift cards for all today","path":["4C"],"packet":"pk3","channel":"Public"})
check("Pat Copy" not in g.allow_senders,"trusted everywhere, then marked spam: trust withdrawn")
# Trust everywhere from People replaces trust on one channel
g.give_verdict({"verdict":"not_spam","status":"held","sender":"Ann Lee","text":"hello all","path":["4C"],"packet":"pk4","channel":"Public","matched":"lockdown"})
check(g.trust_on.get("Ann Lee"),"Ann Lee trusted on Public")
g.action("allow_sender",{"sender":"Ann Lee"})
check("Ann Lee" in g.allow_senders and "Ann Lee" not in g.trust_on,"Trust everywhere replaces it")
g.action("unallow_sender",{"sender":"Ann Lee"})
check("Ann Lee" not in g.allow_senders and "Ann Lee" not in g.trust_on,"Stop trusting clears both")
# Answers that go against strong evidence are asked about first, and nothing changes until confirmed
V=lambda **k: g.give_verdict(dict({"status":"held","path":["4C"],"channel":"Public"},**k))
V(verdict="spam",sender="Spam Box",text="Win a FREE radio, today only!",packet="d1",status="letthrough")
r=V(verdict="not_spam",sender="Other Name",text="win a free radio today only",packet="d2",matched="lockdown")
check(r.get("confirm") and "same message" in r["confirm"] and not g.trust_on.get("Other Name"),"the same text you marked spam: asked first, nothing changed")
r=V(verdict="not_spam",sender="Other Name",text="win a free radio today only",packet="d2",matched="lockdown",confirm=True)
check(r.get("ok") and g.trust_on.get("Other Name"),"confirmed: saved")
r=V(verdict="not_spam",sender="Spam Box",text="hello everyone",packet="d3",matched="lockdown")
check(r.get("confirm") and "marked 1 of Spam Box" in r["confirm"],"a name you marked as spam before: asked first")
g._add_block("text:camp1","text","cheap widgets here","made up","campaign",channel="Public")
r=V(verdict="not_spam",sender="Third Name",text="cheap widgets here now",packet="d4",matched="text:camp1")
check(r.get("confirm") and "campaign" in r["confirm"],"a message held as part of a campaign: asked first")
g.known["Old Timer"]=[time.time()-40*86400,time.time()-60,120]
r=V(verdict="spam",sender="Old Timer",text="morning all",packet="d5",status="letthrough")
check(r.get("confirm") and "Spoofed" in r["confirm"] and "120 messages" in r["confirm"],"spam on a long-standing regular: asked first, with the Spoofed hint")
for i in range(2): V(verdict="not_spam",sender="Kind Soul",text=f"thanks all {i}",packet=f"d6{i}",matched="lockdown")
r=V(verdict="spam",sender="Kind Soul",text="buy now",packet="d7",status="letthrough")
check(r.get("confirm") and "not spam before" in r["confirm"],"spam on a name you marked genuine twice: asked first")
r=V(verdict="not_spam",sender="Plain Newbie",text="first time here",packet="d8",matched="lockdown")
check(r.get("ok") and not r.get("confirm"),"an ordinary answer is not questioned")

# learning progress
g.blocks.pop("lockdown",None); sync(g)
m.add("Kim New","first time here, hello",["4C"],ago=300); sync(g)
p=row("Kim New")
check(p["standing"]=="learning" and p["progress"] and p["progress"]["need_msgs"]==3 and p["progress"]["msgs"]==1,"progress towards known: "+str(p["progress"]))
# saved and loaded
g._save_state(force=True)
g2=guard.__wrapped__(m) if hasattr(guard,"__wrapped__") else None
st=read_state(g.cfg["state_file"]) if os.path.exists(g.cfg["state_file"]+".gz") else {}
check("trust_on" in st and "mark_counts" in st,"saved with the state")
# "new place" warnings: at most every 12 hours per name
g.action("allow_sender",{"sender":"Roamer"})
n0=sum(1 for a in g.activity if "Roamer" in a["msg"] and "new place" in a["msg"])
for i,h in enumerate(["4C","5D","6E","7F"]):
    m.add("Roamer",f"moving about {i}",[h],ago=240-i*10); sync(g)
n1=sum(1 for a in g.activity if "Roamer" in a["msg"] and "new place" in a["msg"])
check(n1-n0==1,f"new-place warnings rate-limited ({n1-n0} in a burst of moves)")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
