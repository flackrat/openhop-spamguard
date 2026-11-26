# Points from the 6.54 review: bot-safe channels set by an earlier version listed for the owner to check (nothing
# changed by itself); the saved-data layout number used when loading; private channels sharing a tag, and one
# becoming readable later; the clock going backwards; the channel's protection kept with each message; service words
# only at a word's edge; openHop's mode age on Health. Made-up names and messages only.
import sys, os, time, json, gzip, glob, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
R=sg.BOT_CHANNEL_RE
for n,want in (("weathered",False),("weathering",False),("ukweather",True),("weatheruk",False),("weatherproof",False),("weather-alerts",True),
               ("aprsnet",True),("quarry-aprs",True),("telemetryhub",False),("quarrytelemetry",True),("wardriving",True),("latest",False)):
    check(bool(R.search(n))==want,"service words at a word's edge only: %s"%n)
# --- bot-safe channels from before 6.55
g=guard(mock()); g.action("add_channel",{"name":"#quarrylounge","key":""}); g.action("add_channel",{"name":"#weather","key":""})
g.botsafe_channels |= {"#quarrylounge","#weather"}; g._save_state(force=True)
path=g.cfg["state_file"]; st=sg.read_state_file(path+".gz")
for k in ("botsafe_review","botsafe_why","state_schema"): st.pop(k,None)
open(path+".gz","wb").write(gzip.compress(json.dumps(st).encode()))
g2=sg.SpamGuard(dict(g.file_cfg))
check(g2.botsafe_review=={"#quarrylounge"},"an older bot-safe channel whose name doesn't say bot is listed to check: %s"%g2.botsafe_review)
check(g2.botsafe_channels>={"#quarrylounge","#weather"},"and nothing is changed by itself")
check(g2.status()["botsafe_review"]==["#quarrylounge"],"the page gets the list")
g2._save_state(force=True); g3=sg.SpamGuard(dict(g.file_cfg))
check(g3.botsafe_review=={"#quarrylounge"},"the list survives a restart until answered")
g3.action("botsafe_keep",{"name":"#quarrylounge"})
check(not g3.botsafe_review and "#quarrylounge" in g3.botsafe_channels and g3.botsafe_why["#quarrylounge"]=="you","Keep bot-safe answers it")
g3._save_state(force=True); g4=sg.SpamGuard(dict(g.file_cfg))
check(not g4.botsafe_review,"and it isn't asked again")
g2.action("channel_blocking",{"name":"#quarrylounge","mode":"full","confirm":True})
check(not g2.botsafe_review and "#quarrylounge" not in g2.botsafe_channels,"Block spam answers it too")
g5=guard(mock()); g5.action("add_channel",{"name":"#quarrylounge","key":""})
g5.action("channel_blocking",{"name":"#quarrylounge","mode":"botsafe"}); g5._save_state(force=True)
g6=sg.SpamGuard(dict(g5.file_cfg)); check(not g6.botsafe_review,"bot-safe chosen in this version isn't asked about")
# --- saved-data layout number
g7=guard(mock()); g7._save_state(force=True); g7._save_state(force=True); p7=g7.cfg["state_file"]
st=sg.read_state_file(p7+".gz"); st["state_schema"]=sg.STATE_SCHEMA+5; st["save_seq"]=st["save_seq"]+10
open(p7+".gz","wb").write(gzip.compress(json.dumps(st).encode()))
g8=sg.SpamGuard(dict(g7.file_cfg))
check(g8._state_newer==sg.STATE_SCHEMA+5 and os.path.exists(p7+".gz.layout%d.keep"%(sg.STATE_SCHEMA+5)),"saved data from a newer version is read, and kept as it was")
check(any("newer version" in w for w in g8.health()["warnings"]),"Health says so")
st["state_schema"]="two"; open(p7+".gz","wb").write(gzip.compress(json.dumps(st).encode()))
g9=sg.SpamGuard(dict(g7.file_cfg)); check(getattr(g9,"_restored_from_backup",False),"an unreadable layout number counts as damaged; the backup is used")
# --- private channels sharing a tag, and one read later
base=sg.channel_hash_byte(sg.hashtag_secret("#quarry0")); twin=None
for i in range(1,5000):
    if sg.channel_hash_byte(sg.hashtag_secret(f"#quarry{i}"))==base: twin=f"#quarry{i}"; break
gA=guard(mock()); gA.chan_cands.clear(); now=time.time()
for n in ("#quarry0",twin):
    p=bytes.fromhex(enc("Quarry Bea","hi",key=sg.hashtag_secret(n))); gA._chan_note(p,None,now)
hk=f"h:{base:02x}"
check(hk in gA.chan_heard and gA.chan_heard[hk]["days"][time.strftime("%Y-%m-%d")][0]==2,"two private channels with one tag are counted together under the tag")
gA.action("add_channel",{"name":"#quarry0","key":""})
p=bytes.fromhex(enc("Quarry Bea","hi again",key=sg.hashtag_secret("#quarry0")))
gA._chan_note(p,sg.decrypt_group_text(p,{"#quarry0":sg.hashtag_secret("#quarry0")}),now)
check(gA.chan_heard[hk]["days"][time.strftime("%Y-%m-%d")][0]==2,"once a key is added, the earlier tag counts stay where they were")
check(gA.chan_heard["n:#quarry0"]["days"][time.strftime("%Y-%m-%d")][0]==1,"and new messages count under the channel's name")
gA._chh_cache=None; names=[r["name"] for r in gA.channels_heard(now)]
check(names.count("#quarry0")==1,"with no duplicate row: %s"%names)
# --- the clock going backwards
gA.chan_key={"day":time.strftime("%Y-%m-%d",time.localtime(now+86400)),"key":"11"*16}
gA.chan_heard["n:#quarry0"]["days"][gA.chan_key["day"]]=[1,1,["aaaabbbb"]]
gA.chan_rotate()
check(gA.chan_key is None and gA.chan_heard["n:#quarry0"]["days"][time.strftime("%Y-%m-%d",time.localtime(now+86400))][2]==[],"a clock set back drops the key and the codes it made")
# --- the channel's protection kept with each message
m=mock(); gB=guard(m); gB.poll_once(); gB.watch_channels.add("Public")
m.add("Quarry Cal","Win a free radio, reply now",["A1","B2"],ago=5); gB.poll_once()
e=[x for x in gB.events if x.sender=="Quarry Cal"][0]
check(e.chan_then=="watch","the channel's protection is kept with the message")
gB.watch_channels.discard("Public")
check("was set to Count only" in (gB.why_through({"packet":e.packet}) or ""),"and the reason uses it after the channel changes")
# --- openHop's mode age on Health
f={x["part"]:x for x in gB.health()["fresh"]}; check("ohmode" in f,"Health shows when openHop's mode was last read")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
