# 6.55.0: a Bot answer, apart from Spam: that one name is held on a channel that blocks spam, its words aren't blocked
# for anyone else and it doesn't teach the spam checks; bot-safe and Count only channels leave it alone. Not spam no
# longer trusts the name unless you choose to, and says a stopped message can't be sent again. A known name isn't
# held for a day over one machine-looking message. New arrivals on People. Made-up names and messages only.
import sys, os, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
m=mock(); g=guard(m); g.poll_once()
item={"sender":"Quarry Weatherbot","text":"Temp 7C wind SW 12 mph","path":"A1>B2","packet":"pk1","channel":"Public","status":"genuine"}
blocks0=set(g.blocks); sense0=len(g.sense_learned); mc0=dict(g.mark_counts)
g.trust_on["Quarry Weatherbot"]={"Public":time.time()}
r=g.give_verdict(dict(item,verdict="bot"))
new=[k for k in g.blocks if k not in blocks0]
check(r["ok"] and "week" in r["message"],"a bot is held on Public for a week: %s"%r["message"])
check(len(new)==1 and g.blocks[new[0]]["source"]=="botmark" and g.blocks[new[0]]["kind"]=="burst" and g.blocks[new[0]].get("channel")=="Public","one hold, on that name on that channel")
check(not any(g.blocks[k]["kind"] in ("text","words") for k in new),"its words aren't blocked for anyone else")
check(len(g.sense_learned)==sense0 and g.mark_counts==mc0,"it doesn't teach the spam checks or count as a spam mark")
check("Quarry Weatherbot" not in g.trust_on,"trust on that channel ends")
check(g.labels.get("pk1")=="bot","the answer is kept as a bot label")
r=g.give_verdict(dict(item,verdict="none")); check(not [k for k in g.blocks if k not in blocks0],"taking it back removes the hold")
g.botsafe_channels.add("#quarrywx"); g.cfg["channels"]["#quarrywx"]=sg.hashtag_secret("#quarrywx")
r=g.give_verdict(dict(item,verdict="bot",channel="#quarrywx",packet="pk2"))
check(not [k for k in g.blocks if k not in blocks0] and "left alone" in r["message"],"on a bot-safe channel bots are left alone: %s"%r["message"])
check(sg.BOT_TRIP_SOURCES>={"botmark"},"a bot hold never applies on a bot-safe channel")
try: g.give_verdict(dict(item,verdict="bot",sender="?")); check(False,"a bot needs a name")
except ValueError: check(True,"a bot needs a name")
# --- Not spam and trust are separate choices
m2=mock(); g2=guard(m2); g2.poll_once()
b={"sender":"Quarry Pat","text":"see you at the field day","path":"A1>B2","packet":"pk3","channel":"Public"}
r=g2.give_verdict(dict(b,verdict="not_spam",status="genuine",trust="none"))
check("Quarry Pat" not in g2.allow_senders and "Quarry Pat" not in g2.trust_on,"Not spam on its own trusts nobody")
r=g2.give_verdict(dict(b,verdict="not_spam",status="genuine",trust="channel",packet="pk4"))
check(g2.trust_on.get("Quarry Pat",{}).get("Public"),"trust on this channel when you choose it")
r=g2.give_verdict(dict(b,verdict="not_spam",status="genuine",trust="everywhere",sender="Quarry Lee",packet="pk5"))
check("Quarry Lee" in g2.allow_senders,"or everywhere")
g2.machine_block_key=None
k="machine:test1"; g2._add_block(k,"burst","Quarry Sam","Sends messages that look like a program, not chat","machine",channel="Public",ttl=86400,from_ts=time.time())
r=g2.give_verdict(dict(b,sender="Quarry Sam",verdict="not_spam",status="held",matched=k,trust="none",packet="pk6"))
check(k not in g2.blocks and "Quarry Sam" not in g2.trust_on and "Quarry Sam" not in g2.allow_senders,"a held message marked fine lifts the hold that caught it, without trusting the name")
check("can't be sent again" in r["message"],"and says a stopped message can't be sent again: %s"%r["message"])
try: g2.give_verdict(dict(b,verdict="not_spam",trust="always")); check(False,"an unknown trust choice is refused")
except ValueError: check(True,"an unknown trust choice is refused")
check("trust the name" not in (g2._mark_doubt("not_spam","Quarry Sam","x",{}) or ""),"the double-check no longer says it will trust the name")
# --- a known name isn't held for a day over one machine-looking message
m3=mock(); g3=guard(m3, machine_block="all"); g3.poll_once()
m3.add("Quarry Known","hello all, good morning",["A1","B2"],ago=600); g3.poll_once()
check(g3.is_known("Quarry Known"),"a name SpamGuard knows")
n0=len(g3.blocks)
m3.add("Quarry Known","AAAAQkFTRTY0LWVuY29kZWQtYmxvYi1vZi1kYXRhLWZvci10ZXN0aW5nLW9ubHk=",["A1","B2"],ago=5); g3.poll_once()
check(not any(b["source"]=="machine" and b["value"]=="Quarry Known" for b in g3.blocks.values()),"isn't held as a machine for a day")
m3.add("Quarry Newmachine","AAAAQkFTRTY0LWVuY29kZWQtYmxvYi1vZi1kYXRhLWZvci10ZXN0aW5nLW9ubHk=",["A1","B2"],ago=4); g3.poll_once()
check(any(b["source"]=="machine" and b["value"]=="Quarry Newmachine" for b in g3.blocks.values()) or not any(e.machine for e in g3.events if e.sender=="Quarry Newmachine"),"a new name sending machine messages still is")
# --- new arrivals
now=time.time()
g2.known["Quarry Fresh"]=[now-3600,now-60,2]; g2.known["Quarry Older"]=[now-20*86400,now-60,40]; g2.known["Quarry Newer"]=[now-600,now-60,1]
p=g2.people({"show":"new"}); names=[r["name"] for r in p["rows"]]
check("Quarry Fresh" in names and "Quarry Older" not in names,"New arrivals lists names first heard this week only: %s"%names)
check(names.index("Quarry Newer")<names.index("Quarry Fresh"),"newest first")
check(p["counts"]["new"]>=2,"with a count for its chip")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
