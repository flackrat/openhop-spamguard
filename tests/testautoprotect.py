# A new SpamGuard left in Monitor switches itself to Protect once it has watched long enough and seen enough
# spam, unless you marked something as genuine, too many genuine-looking messages were held, or you chose
# Monitor yourself. All data made up.
import sys, logging, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def fresh():
    m=mock(); g=guard(m, mode="monitor"); return m,g
m,g=fresh()
check(g.cfg["mode"]=="monitor" and g.cfg["auto_protect"] is True,"starts in Monitor with the automatic switch on")
s=g.auto_protect_status(); check(s and s["due"]>=time.time()+70*3600,"no spam yet: due after three days")
now=time.time()
g.monitor_since=now-25*3600
for i in range(12): g.catches.append(now-3600+i)
s=g.auto_protect_status(); check(s["due"]<=time.time()+1 and not s["waiting"],"a day plus enough spam: due now: "+str(s))
g._auto_checked=0; g._maybe_auto_protect()
check(g.cfg["mode"]=="protect","switched itself to Protect")
check(any("Switched to Protect by itself" in a["msg"] for a in g.activity),"says so in Activity")
check(g.auto_protect_status() is None,"nothing more to do once in Protect")
# marked as genuine -> leave it to the user
m,g=fresh(); g.monitor_since=now-25*3600
for i in range(12): g.catches.append(now-3600+i)
g.action("not_spam",{"sender":"Canal Boat Ted","text":"hello"})
s=g.auto_protect_status(); check(s["waiting"] and "genuine" in s["waiting"],"waits when you marked something genuine")
g._auto_checked=0; g._maybe_auto_protect(); check(g.cfg["mode"]=="monitor","stays in Monitor")
# too many held
m,g=fresh(); g.monitor_since=now-25*3600
for i in range(12): g.catches.append(now-3600+i)
for i in range(5): g.held.append({"ts":now-100,"sender":f"Name{i}","text":"hi","path":"A7","why":"x","matched":"k","packet":"p"})
check(g.auto_protect_status()["waiting"],"waits when several genuine-looking messages were held")
# not enough time yet
m,g=fresh(); g.monitor_since=now-3*3600
for i in range(50): g.catches.append(now-60+i)
g._auto_checked=0; g._maybe_auto_protect(); check(g.cfg["mode"]=="monitor","never before a full day of watching")
# you chose Monitor after Protect -> switch is turned off
m,g=fresh(); g.apply_settings({"mode":"protect"}); g.apply_settings({"mode":"monitor"})
check(g.cfg["auto_protect"] is False and g.auto_protect_status() is None,"choosing Monitor yourself turns it off")
# Stay in Monitor button
m,g=fresh(); g.apply_settings({"auto_protect":False}); check(g.auto_protect_status() is None,"Stay in Monitor turns it off")
st=g.status(); check("auto_protect" in st,"page told about it")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
