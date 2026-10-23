# Reporting: names that carry on another name's repeat count shown together, the "Most held, last 7 days"
# table, airtime per day, where FloodGuard's stopped floods came into the mesh, and one-tap labels.
# All names, messages and repeater codes are made up.
import sys, logging, json, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def cycle(g):
    g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()

TEXT="Reminder that the club net is on Thursday evenings at eight, everyone is welcome to join in"

# 1. A name that carries on another's count: the block, Activity and the most-held table say so
m=mock(); g=guard(m, long_window_seconds=86400); g.apply_settings({"mode":"protect"})
for i in range(3): m.add("Rowan Hill",TEXT,["4C","2F"],ago=15000-i*3000)
m.add("Rowan Hill again",TEXT,["4C","2F"],ago=600)
cycle(g)
b=[b for b in g.blocks.values() if b.get("source")=="slowrepeat"]
check(b and b[0].get("after")==["Rowan Hill"],"the block remembers the earlier name: "+str(b))
check(any("carrying on from Rowan Hill" in a["msg"] for a in g.activity),"Activity says which name it carried on from")
check(g.name_links.get("Rowan Hill again",{}).get("after")==["Rowan Hill"],"the link is kept")
m.add("Rowan Hill again",TEXT,["4C","2F"],ago=-2)
cycle(g)
for e in list(g.events): g._count(e)
mh=g.metrics()["most_held"]
row=[r for r in mh if r["name"]=="Rowan Hill again"]
check(row and "Rowan Hill" in row[0].get("also",[]),"most-held shows both names as one row: "+str(mh))
check(not any(r["name"]=="Rowan Hill" for r in mh),"the earlier name isn't listed separately")
check(row and row[0]["held"]>=1 and row[0]["messages"]>=5,"held copies and messages are counted: "+str(row))
st=json.dumps(g.status())
check("Thursday evenings" not in json.dumps(mh),"the table holds counts only, never message text")

# 2. Restart keeps the counts and links
g._save_state(force=True)
g2=sg.SpamGuard({"state_file":g.cfg["state_file"],"openhop_url":g.cfg["openhop_url"],"api_key":"t","mode":"protect"})
check(g2.name_links.get("Rowan Hill again"),"links survive a restart")
check(any(r["name"]=="Rowan Hill again" for r in g2.metrics()["most_held"]),"most-held survives a restart")

# 3. Clearing the spam history clears the table
g.action("clear_history",{"confirm":"RESET"})
check(g.metrics()["most_held"]==[],"clear history empties the most-held table")

# 4. Airtime per day and where stopped floods came in
m3=mock(); g3=guard(m3); g3.apply_settings({"mode":"protect","floodguard":True})
g3.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":32}
g3.rule_ids["flood:limit"]=4242
now=time.time()
def pk(i,path,stopped):
    return {"timestamp":now-600+i,"length":60,"route":1,"type":5,"original_path":json.dumps(path),
            "drop_reason":"Policy blocked packet (rule 4242)" if stopped else "","transmitted":not stopped,"rssi":-90}
for i in range(12): g3.fg_observe(pk(i,["9A","31","2F"],True))
for i in range(5): g3.fg_observe(pk(20+i,["B2","2F"],True))
for i in range(7): g3.fg_observe(pk(40+i,["C7","2F"],False))
mt=g3.metrics()
fs=mt["flood_sources"]
check([s["hop"] for s in fs]==["9A","B2"] and fs[0]["d7"]==12 and fs[0]["d1"]==12,"stopped floods by first repeater: "+str(fs))
check(not any(s["hop"]=="C7" for s in fs),"packets passed on aren't counted as floods stopped")
today=mt["daily"][-1]
check(today["ar"]>0 and today["fs"]>0,"airtime used and saved by FloodGuard per day: "+str(today))
check(all(k in mt["daily"][0] for k in ("ar","sa","fs")),"every day has the airtime figures")

# 5. One-tap labels: recorded, shown, cleared, and nothing is blocked or trusted
m4=mock(); g4=guard(m4); g4.apply_settings({"mode":"protect"})
m4.add("Quarry Pete","Anyone near the canal this afternoon?",["4C","2F"],ago=300)
cycle(g4)
rec=g4.status()["recent"][0]
before=(len(g4.blocks),set(g4.allow_senders))
r=g4.action("label",{"label":"spam","sender":rec["sender"],"text":rec["text"],"path":rec["path"],"packet":rec["packet"]})
check(g4.status()["recent"][0]["label"]=="spam","the label shows on the message")
check((len(g4.blocks),set(g4.allow_senders))==before,"labelling blocks and trusts nothing")
g4.action("label",{"label":"not_spam","sender":rec["sender"],"text":rec["text"],"packet":rec["packet"]})
check(g4.status()["recent"][0]["label"]=="not_spam","a label can be changed")
g4.action("label",{"label":"none","sender":rec["sender"],"text":rec["text"],"packet":rec["packet"]})
check(not g4.status()["recent"][0]["label"],"and cleared")
try:
    g4.action("label",{"label":"maybe","packet":rec["packet"]}); check(False,"a made-up label is refused")
except ValueError:
    check(True,"")
g4.action("label",{"label":"spam","sender":rec["sender"],"text":rec["text"],"packet":rec["packet"]})
g4._save_state(force=True)
g5=sg.SpamGuard({"state_file":g4.cfg["state_file"],"openhop_url":g4.cfg["openhop_url"],"api_key":"t","mode":"protect"})
check(g5.labels.get(rec["packet"])=="spam","labels survive a restart")

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
