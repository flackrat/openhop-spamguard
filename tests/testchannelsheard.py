# Channels heard: every channel tag counted per day, #hashtag names worked out from mentions and well-known
# names (confirmed by two good decrypts), found channels counted but never logged,
# ranked busiest first, retired after 30 days, and kept across a restart. Made-up names and messages only.
import sys, os, time, json, hashlib, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def group_payload(secret_hex, sender, text, ts=None):
    return bytes.fromhex(enc(sender, text, key=secret_hex, sent=ts))   # the shared helper builds radio packets
g=guard(mock()); now=time.time()
pub=g.cfg["channels"]["Public"]
# Public, read: someone mentions a channel
g._chan_note(group_payload(pub,"Quarry Ann","come over to #quarrychat later"), sg.decrypt_group_text(group_payload(pub,"Quarry Ann","come over to #quarrychat later"),g.cfg["channels"]), now)
check("#quarrychat" in g.chan_cands,"a #name mentioned on a read channel is remembered to try")
qc=sg.hashtag_secret("#quarrychat")
p1=group_payload(qc,"Quarry Bob","hello there"); p2=group_payload(qc,"Quarry Cy","evening all"); p3=group_payload(qc,"Quarry Bob","still here")
check(sg.decrypt_group_text(p1,g.cfg["channels"]) is None,"SpamGuard can't read that channel itself")
for p in (p1,p2,p3): g._chan_note(p, None, now)
L={r["name"]:r for r in g.channels_heard(now)}
check("#quarrychat" in L and L["#quarrychat"]["kind"]=="found","after two good decrypts the channel is named and marked found")
check(L["#quarrychat"]["d7"]==2 and L["#quarrychat"]["names_day"]==2,"messages after it is named are counted under its name: %s"%L.get("#quarrychat"))
check(any(r["kind"]=="unnamed" and r["d7"]==1 for r in L.values()),"the first one, before it was confirmed, stays under its tag")
# a well-known channel is found without anyone mentioning it
pg=sg.hashtag_secret("#ping")
for i in range(3): g._chan_note(group_payload(pg,f"Quarry P{i}","ping"), None, now)
check("#ping" in {r["name"] for r in g.channels_heard(now)},"a well-known channel is named from traffic alone")
# a private channel stays unnamed, with its tag
priv="0123456789abcdef0123456789abcdef"
for i in range(5): g._chan_note(group_payload(priv,"Quarry Dee","private chat"), None, now)
un=[r for r in g.channels_heard(now) if r["kind"]=="unnamed"]
check(any(r["d7"]==5 for r in un),"a private channel is counted by its tag, never named")
# ranking and read channels
for i in range(9): g._chan_note(group_payload(pub,f"Quarry R{i}","morning"), sg.decrypt_group_text(group_payload(pub,f"Quarry R{i}","morning"),g.cfg["channels"]), now)
R=g.channels_heard(now)
check(R[0]["name"]=="Public" and R[0]["kind"]=="read","busiest first; channels SpamGuard reads say so")
check([r["d7"] for r in R]==sorted([r["d7"] for r in R],reverse=True),"ranked by this week's messages")
check(len(R[0]["spark"])==14 and R[0]["spark"][-1]==10,"a 14-day line for each")
# nothing from found channels is logged
logged=[]; g.ev=lambda r: logged.append(r)
g._chan_note(group_payload(qc,"Quarry Bob","another"), None, now)
check(not logged,"found channels' messages aren't logged")
st=json.dumps(g.state_dict())
check("hello there" not in st and "evening all" not in st,"and their text isn't kept")
# kept across a restart; protecting a found channel carries its counts over
g._save_state(force=True); g3=sg.SpamGuard(dict(g.file_cfg))
check("#quarrychat" in {r["name"] for r in g3.channels_heard(now)},"counts survive a restart")
g3.action("add_channel",{"name":"#quarrychat","key":""})
r=[x for x in g3.channels_heard(now) if x["name"]=="#quarrychat"][0]
check(r["kind"]=="read" and r["d7"]>=2,"protecting it keeps its history and marks it read")
# retired after 30 days, unless SpamGuard reads it
old=now+31*86400
R2={r["name"] for r in g.channels_heard(old)}
check("#quarrychat" not in R2 and not any(n.startswith("Unnamed") for n in R2),"channels quiet for 30 days drop off")
g2=guard(mock()); g2._chan_note(group_payload(pub,"Quarry Ann","hi"),sg.decrypt_group_text(group_payload(pub,"Quarry Ann","hi"),g2.cfg["channels"]),now)
g2.channels_heard(old); check(any(e.get("name")=="Public" for e in g2.chan_heard.values()),"a channel SpamGuard reads stays")
# switched off: nothing counted
g4=guard(mock()); g4.cfg["channel_discovery"]=False
check(g4._channels_heard_cached(now)==[],"switched off: no list")
# bot and test channels: protected as count only, and blocking there asks first (or is never allowed)
gb=guard(mock())
check(gb.bot_channel("#weather") and gb.bot_channel("#test") and gb.bot_channel("#mc-radar"),"bot, test and service names are recognised")
check(gb.bot_channel("#ridgeline") is None and gb.bot_channel("Public") is None,"ordinary chat channels aren't")
gb.chan_heard["n:#quarrynet"]={"name":"#quarrynet","hash":1,"first":now,"last":now,"days":{time.strftime("%Y-%m-%d"):[300,4,[]]}}
check("bots" in (gb.bot_channel("#quarrynet") or ""),"a channel where a few names send most messages looks like bots")
out=gb.action("add_channel",{"name":"#weather","key":""})
check("#weather" in gb.botsafe_channels and "#weather" not in gb.watch_channels and "bot-safe" in out.get("message",""),"a bot channel gets bot-safe protection, and says why: %s"%out.get("message"))
gb.action("add_channel",{"name":"#ridgeline","key":""})
check("#ridgeline" not in gb.watch_channels and "#ridgeline" not in gb.botsafe_channels,"an ordinary channel is protected as normal")
r=gb.action("channel_blocking",{"name":"#weather","mode":"full"})
check(r.get("confirm") and "#weather" in gb.botsafe_channels,"full blocking there asks first, and changes nothing yet")
gb.action("channel_blocking",{"name":"#weather","mode":"full","confirm":True})
check("#weather" not in gb.botsafe_channels and "#weather" not in gb.watch_channels,"once you confirm, full blocking")
gb.action("channel_blocking",{"name":"#weather","mode":"watch"})
check("#weather" in gb.watch_channels,"count only is still a choice")
r=gb.action("channel_blocking",{"name":"#weather","mode":"botsafe"})
check(not r.get("confirm") and "#weather" in gb.botsafe_channels and "#weather" not in gb.watch_channels,"bot-safe never needs asking")
gb.cfg["bot_channel_guard"]="never"
try: gb.action("channel_blocking",{"name":"#weather","mode":"full"}); check(False,"never: blocking refused")
except ValueError as e: check("Bot and test channels" in str(e),"never: blocking there is refused, saying where to change it")
gb.cfg["bot_channel_guard"]="off"
r=gb.action("channel_blocking",{"name":"#weather","mode":"full"})
check(not r.get("confirm") and "#weather" not in gb.botsafe_channels,"off: treated like any channel")
gb.cfg["bot_channel_guard"]="ask"
pw=group_payload(sg.hashtag_secret("#weather"),"Quarry Wx","temp 9C")
gb._chan_note(pw, sg.decrypt_group_text(pw,gb.cfg["channels"]), now)
check([x for x in gb.channels_heard(now) if x["name"]=="#weather"][0]["bots"],"the ranking marks it as mostly bots")

# bot-safe in action: bots repeating themselves aren't blocked there, spam with links still is
from harness import mock as _mock
m2=_mock(); g5=guard(m2); g5.apply_settings({"mode":"protect"})
g5.action("add_channel",{"name":"#ping-quarry","key":""})
check("#ping-quarry" in g5.botsafe_channels,"a ping channel is bot-safe")
blocks_before=set(g5.blocks)
want_res=[]
g5._add_block("rep:x","text","pong from quarry bot","made-up","repeat","#ping-quarry",3600,None)
g5._add_block("lnk:x","links",["qspam.example"],"made-up","links","#ping-quarry",3600,None)
bs={k:b for k,b in g5.blocks.items() if k in ("rep:x","lnk:x")}
check(g5._block_channels(bs["rep:x"])==[] ,"a repeat block on a bot-safe channel covers no channels")
check(g5._block_channels(bs["lnk:x"])==["#ping-quarry"],"a link block there still applies")
# through openHop's real rule engine: the bot's repeated reply goes out, the link spam doesn't
g5._add_block("rep:all","text","pong from quarry bot","made-up","repeat",sg.ALL_CHANNELS,3600,None)
g5.last_sync=0; g5.sync_pending=True; g5.poll_once()
PQ=sg.hashtag_secret("#ping-quarry")
check(m2.decide("Quarry Bot","pong from quarry bot",["4C"],key=PQ)!="drop","the bot's reply still goes out on the bot-safe channel, even under an every-channel repeat block")
check(m2.decide("Quarry Ann","pong from quarry bot",["4C"])=="drop","the same repeat block still stops it on Public")
check(m2.decide("QX7ZP9","deals at qspam.example now",["4C"],key=PQ)=="drop","link spam is still stopped on the bot-safe channel")

print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
