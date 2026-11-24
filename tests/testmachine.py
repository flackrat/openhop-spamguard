# Messages that are a program talking (a Reticulum bridge over a channel) are counted and labelled, and held only
# when you choose to stop them (experimental). All names and data are made up.
import sys, os, base64, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
b64=lambda n: base64.urlsafe_b64encode(os.urandom(n)).decode().rstrip("=")
Z85="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#"
def z85(data):   # (base64.z85encode only exists from Python 3.13)
    out=[]
    for i in range(0,len(data)-len(data)%4,4):
        v=int.from_bytes(data[i:i+4],"big"); s=""
        for _ in range(5): s=Z85[v%85]+s; v//=85
        out.append(s)
    return "".join(out)
check(sg.machine_kind("RNS:"+b64(48))=="reticulum","an RNS: fragment is spotted")
check(sg.machine_kind(b64(75))=="encoded" and sg.machine_kind(z85(os.urandom(76)))=="encoded","a long unbroken encoded run is spotted")
for t in ("Morning all, repeater check from the hill","https://www.example.com/a/very/long/link/that/goes/on/and/on/and/on/and/on/forever12345","RNS: is a nice protocol","Supercalifragilisticexpialidocious"*3,"hello"):
    check(sg.machine_kind(t) is None,"ordinary text is not: %s"%t[:30])

m=mock(); g=guard(m, floodguard=False); g.apply_settings({"mode":"protect"})
for i in range(5): m.add("Bridge Node One","RNS:"+b64(48),["4C","2F"],ago=300-i*30)
m.add("Plain Person","Anyone on the hill today?",["4C","2F"],ago=100)
cycle(g)
check(g.stats.get("machine",0)==5,"five machine messages counted (%s)"%g.stats.get("machine"))
check(g.status()["summary"]["machine_24h"]==5,"shown in the summary")
check(not any("machine" in str(b.get("reason","")).lower() for b in g.blocks.values()),"no block is written because it is machine traffic")
notes=[n for n in g.notes if "program talking" in str(n)] if hasattr(g,"notes") else []
check(len(notes)<=1,"mentioned once a day at most")
check(m.decide("Bridge Node One","RNS:"+b64(48),["4C","2F"])=="allow","a fresh fragment from a new name is passed on")
why=g._q_classify({"machine":"reticulum","known":False})
check(why[0]=="genuine" and "program talking" in why[1],"the Messages list explains it: %s"%(why,))
# Experimental: stop them. Public only, or every channel; Reticulum from the first message, other kinds per name.
check(g.cfg["machine_block"]=="off" and not g._build_machine(),"off by default: no rule")
m=mock(); g=guard(m, floodguard=False, channels={"Public":sg.PUBLIC_CHANNEL_KEY,"#bridge":"0123456789abcdef0123456789abcdef"})
g.apply_settings({"mode":"protect","machine_block":"public"})
check(len(g._build_machine())==1,"Public only: one standing rule")
check(m.decide("Bridge Node Two","RNS:"+b64(48),["4C","2F"])=="drop","a Reticulum fragment is stopped from the first one")
check(m.decide("Bridge Node Two","RNS:"+b64(48),["4C","2F"],key="0123456789abcdef0123456789abcdef")=="allow","but not on another channel with Public only")
check(m.decide("Plain Person","Anyone on the hill today?",["4C","2F"])=="allow","chat still passes")
blob=b64(75)
m.add("Packet Pusher Q",blob,["4C","2F"],ago=200)
cycle(g)
held=[b for b in g.blocks.values() if b.get("source")=="machine"]
check(len(held)==1 and held[0]["value"]=="Packet Pusher Q" and held[0]["channel"]=="Public","an encoded run holds that name on Public: %s"%held)
check(m.decide("Packet Pusher Q",b64(75),["4C","2F"])=="drop","its next ones are stopped")
for i in range(6): m.add("Chatty Known Q",f"Evening all, update {i} from the hill",["4C","2F"],ago=150-i*10)
cycle(g); check(g.is_known("Chatty Known Q"),"a known name")
m.add("Chatty Known Q",b64(80),["4C","2F"],ago=30); cycle(g)
check(m.decide("Chatty Known Q",b64(80),["4C","2F"])=="drop","known names are stopped too: you chose it")
g.allow_senders.add("Trusted Bridge Q")
m.add("Trusted Bridge Q",b64(75),["4C","2F"],ago=20); cycle(g)
check(not any(b.get("value")=="Trusted Bridge Q" for b in g.blocks.values()),"a name you trust from People is not held")
k=next(k for k,b in g.blocks.items() if b.get("value")=="Packet Pusher Q")
g.action("not_spam",{"sender":"Packet Pusher Q","text":blob,"channel":"Public","matched":k,"packet":""})
m.add("Packet Pusher Q",b64(75),["4C","2F"],ago=5); cycle(g)
check(not any(b.get("value")=="Packet Pusher Q" for b in g.blocks.values()),"Not spam on a held one lets that name through again")
g.apply_settings({"machine_block":"all"})
check(m.decide("Bridge Node Three","RNS:"+b64(48),["4C","2F"],key="0123456789abcdef0123456789abcdef")=="drop","every channel: stopped on the others too")
g.watch_channels.add("#bridge"); g.last_sync=0; g.sync_pending=True; g.poll_once()
check(m.decide("Bridge Node Three","RNS:"+b64(48),["4C","2F"],key="0123456789abcdef0123456789abcdef")=="allow","except a channel you only read")
g.watch_channels.discard("#bridge")
g.apply_settings({"mode":"monitor"})
check(all(r["then"]["action"]=="log_only" for r in g._build_machine()),"Monitor mode only records")
g.apply_settings({"machine_block":"off","mode":"protect"})
check(not g._build_machine() and m.decide("Bridge Node Three","RNS:"+b64(48),["4C","2F"])=="allow","off again: the rule goes")
check(g.status()["summary"]["machine_stop"] is False and "machine_by_hour" not in g.status()["summary"],"the page is told; no hourly dots")
print("testmachine: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
