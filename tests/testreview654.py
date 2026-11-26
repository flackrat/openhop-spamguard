# Points from the 6.53 review: traffic alone never makes a channel bot-safe; sender codes dropped when the day
# changes by the Pi's clock, even with no messages, and late packets from another day aren't coded; trust as it was
# when a message arrived; an old reading of openHop's mode isn't treated as current; schema numbers on the export
# and saved state; save numbers checked strictly. Made-up names and messages only.
import sys, os, time, json, gzip, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
now=time.time(); today=time.strftime("%Y-%m-%d"); yday=time.strftime("%Y-%m-%d",time.localtime(now-86400))
# --- bot channels: traffic is a hint only
g=guard(mock())
g.chan_heard["n:#quarrylounge"]={"name":"#quarrylounge","hash":1,"first":now-86400,"last":now,"days":{today:[300,3,[]]}}
check(g.bot_channel("#quarrylounge") and not g.bot_name("#quarrylounge"),"busy with few names looks automated, but the name doesn't say so")
r=g.action("add_channel",{"name":"#quarrylounge","key":""})
check("#quarrylounge" not in g.botsafe_channels,"traffic alone doesn't make a channel bot-safe")
r=g.action("channel_blocking",{"name":"#quarrylounge","mode":"full"})
check(r.get("ok",True) is not False,"and full blocking there needs no extra confirmation")
g._chh_cache=None; row={x["name"]:x for x in g.channels_heard(now)}["#quarrylounge"]
check(row["bots_by"]=="traffic","the list says it's only traffic: %s"%row.get("bots_by"))
g.action("add_channel",{"name":"#quarry-wx","key":""}); g._chh_cache=None
check({x["name"]:x for x in g.channels_heard(now)}["#quarry-wx"]["bots_by"]=="name","a name match says so")
# --- sender codes by the Pi's clock
pub=g.cfg["channels"]["Public"]
p=bytes.fromhex(enc("Quarry Ann","hello",key=pub)); g._chan_note(p,sg.decrypt_group_text(p,{"Public":pub}),now)
check(g.chan_key and g.chan_key["day"]==today and g.chan_heard["n:Public"]["days"][today][2],"today's sender coded with today's key")
g.chan_key["day"]=yday; g.chan_heard["n:Public"]["days"][today][2]=["abcd1234"]
g.chan_heard["n:Public"]["days"][today][2]=["abcd1234"]
g.chan_rotate()
check(g.chan_key is None,"the key goes once the day changes, with no message needed")
d=g.chan_heard["n:Public"]["days"]
d[yday]=[5,2,["11112222","33334444"]]; g.chan_key={"day":yday,"key":"00"*16}; g.chan_rotate()
check(d[yday][2]==[] and d[yday][1]==2,"yesterday's codes deleted, its count kept")
p=bytes.fromhex(enc("Quarry Late","hello",key=pub)); g._chan_note(p,sg.decrypt_group_text(p,{"Public":pub}),now-86400)
check(d[yday][0]==6 and d[yday][2]==[] and d[yday][1]==2,"a late packet from yesterday is counted, but not coded")
check(g.chan_key is None or g.chan_key["day"]==today,"and doesn't bring back yesterday's key")
# --- trust as it was
m=mock(); g2=guard(m); g2.poll_once(); g2.allow_senders.add("Quarry Pal")
m.add("Quarry Pal","Win a free radio, reply now",["A1","B2"],ago=5); g2.poll_once()
e=[x for x in g2.events if x.sender=="Quarry Pal"][0]
check(e.trust_then=="everywhere","trust kept with the message")
g2.allow_senders.discard("Quarry Pal")
w=g2.why_through({"packet":e.packet}); check(w and "was trusted" in w,"untrusting later doesn't change the reason: %s"%w)
m.add("Quarry Other","Win a free radio, reply now please",["A1","B2"],ago=3); g2.poll_once()
e2=[x for x in g2.events if x.sender=="Quarry Other"][0]; g2.allow_senders.add("Quarry Other")
check("trusted" not in (g2.why_through({"packet":e2.packet}) or ""),"trusting later doesn't either")
# --- openHop's mode goes stale
m.oh_mode="no_tx"; g2.oh_mode_ts=0; g2.refresh_oh_mode(); g2.loop_beat=time.time()
check(g2.oh_mode_now()=="no_tx" and g2.status()["openhop_mode"]=="no_tx","a fresh reading is used")
g2.oh_mode_ok=time.time()-3600
p=g2.protection(); rp=next(x for x in p["parts"] if x["part"]=="repeating")
check(g2.oh_mode_now() is None and p["state"]!="idle" and rp["text"]=="Not known lately","an hour-old reading isn't current: %s"%rp["text"])
check(g2.status()["openhop_mode"] is None,"and the Mode card stops warning on it")
# --- schema numbers and strict save numbers
check(g2.diagnostics()["schema"]==sg.DIAG_SCHEMA,"the export carries its layout number")
g2._save_state(force=True); st=sg.read_state_file(g2.cfg["state_file"]+".gz")
check(st["state_schema"]==sg.STATE_SCHEMA and isinstance(st["save_seq"],int),"saved state carries its layout number")
for bad in (True,-3,"7",2**60,1.5):
    st2=dict(st,save_seq=bad); open(g2.cfg["state_file"]+".gz","wb").write(gzip.compress(json.dumps(st2).encode()))
    g3=sg.SpamGuard(dict(g2.file_cfg)); check(g3.save_seq==0,"a bad save number is ignored: %r"%(bad,))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
