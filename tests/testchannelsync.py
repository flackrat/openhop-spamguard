# Your own blocks on every channel, and carrying your decisions to a second SpamGuard. Checked against
# openHop's own rule engine. All names, messages, channels and repeater codes are made up.
import sys, logging, json, os
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PUB=sg.PUBLIC_CHANNEL_KEY
TRAIL=sg.hashtag_secret("trailchat"); BOATS=sg.hashtag_secret("boatyard")
class P:
    def __init__(s,text,sender,path,key):
        s.payload=bytearray(bytes.fromhex(enc(sender,text,key))); s.transport_codes=[0,0]; s.p=path
    def get_path_hashes_hex(s): return s.p
    def get_payload_type(s): return 5
    def get_payload(s): return s.payload
def act(m,text,sender,path,key=PUB):
    return PolicyEngine(m.policy["policy_engine"]).evaluate(P(text,sender,path,key),{"payload_type":5,"hop_count":len(path),
        "route_type":1,"local_transmission":False}).action
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
def three(m):
    g=guard(m,floodguard=False); g.apply_settings({"mode":"protect"})
    g.action("add_channel",{"name":"#trailchat","key":TRAIL}); g.action("add_channel",{"name":"#boatyard","key":BOATS})
    sync(g); return g

# A mute on every channel: one block, held on each channel SpamGuard reads, the same in openHop and locally
m=mock(); g=three(m)
g.action("mute",{"sender":"Zed Quill","channel":"Public","days":7})
g.action("mute",{"sender":"Zed Quill","channel":"*","days":7}); sync(g)
mutes=[b for b in g.blocks.values() if b["kind"]=="burst" and b["value"]=="Zed Quill"]
check(len(mutes)==1 and mutes[0]["channel"]=="*","one mute for every channel replaces the single-channel one")
for key,name in ((PUB,"Public"),(TRAIL,"#trailchat"),(BOATS,"#boatyard")):
    check(act(m,"buy widgets","Zed Quill",["A1"],key)=="drop",f"muted on {name} in openHop")
check(act(m,"hello","Ann Hill",["A1"],TRAIL)=="allow","other names still get through")
for key in (PUB,TRAIL): m.add("Zed Quill","buy widgets today",["A1"],key=key)
g.poll_once()
check(all(e.matched for e in g.events if e.sender=="Zed Quill"),"and SpamGuard's own count agrees on each channel")
check("every channel" in g.describe(mutes[0]),"the block says it covers every channel")

# A single-channel mute stays on its channel, in openHop and in SpamGuard's own count
m2=mock(); g2=three(m2)
g2.action("mute",{"sender":"Lou Park","channel":"#trailchat","days":7}); sync(g2)
check(act(m2,"x","Lou Park",["A1"],TRAIL)=="drop" and act(m2,"x","Lou Park",["A1"],PUB)=="allow","one channel only")
m2.add("Lou Park","just saying hello",["A1"]); g2.poll_once()
check(not any(e.matched for e in g2.events if e.sender=="Lou Park"),"not counted as held on Public")

# A text block you added only applies on its channel locally too (it used to count on every channel)
g2.action("block_text",{"text":"cheap widgets for sale now","channel":"#boatyard"}); sync(g2)
m2.add("Kim Lane","cheap widgets for sale now",["B2"]); g2.poll_once()
check(not any(e.matched for e in g2.events if e.sender=="Kim Lane"),"text block on #boatyard doesn't count on Public")
check(act(m2,"cheap widgets for sale now","Kim Lane",["B2"],BOATS)=="drop","and it holds on #boatyard")
k=next(k for k,b in g2.blocks.items() if b["kind"]=="text")
g2.action("block_channel",{"key":k,"channel":"*"}); sync(g2)
check(act(m2,"cheap widgets for sale now","Kim Lane",["B2"],PUB)=="drop","moved to every channel from Blocks")
try: g2.action("block_channel",{"key":k,"channel":"#nowhere"}); bad=False
except ValueError: bad=True
check(bad,"a channel SpamGuard doesn't read is refused")
g2._add_block("repeat:x","repeat","some repeated words","test","repeat",channel="Public",extra={"who":"Max Dale"})
try: g2.action("block_channel",{"key":"repeat:x","channel":"*"}); bad=False
except ValueError: bad=True
check(bad,"blocks SpamGuard made itself can't be moved")

# A copy hold on every channel
g2.action("hold_name_hop",{"sender":"Ann Hill","hop":"E7","channel":"*"}); sync(g2)
check(act(m2,"x","Ann Hill",["E7","9B"],TRAIL)=="drop" and act(m2,"x","Ann Hill",["E7","9B"],PUB)=="drop","copy hold on every channel")
check(act(m2,"x","Ann Hill",["4C"],TRAIL)=="allow","the real person gets through elsewhere")

# A block for a channel that is later removed stops, instead of moving onto Public
m3=mock(); g3=three(m3)
g3.action("mute",{"sender":"Ned Ford","channel":"#boatyard","days":7}); sync(g3)
g3.action("remove_channel",{"name":"#boatyard"})
sync(g3)
check(act(m3,"x","Ned Ford",["A1"],PUB)=="allow","a removed channel's mute doesn't hold the name on Public")

# Export from one SpamGuard, import on another: added, merged, never shortened, no channel keys
g2.allow_senders.add("Oli West"); g2.allow_texts.add("net check tonight"); ex=g2.export_decisions()
blob=json.dumps(ex)
check(TRAIL not in blob and BOATS not in blob and PUB not in blob,"no channel keys in the export")
check(ex["format"]=="spamguard-decisions" and not any(b["kind"]=="repeat" for b in ex["blocks"]),"only your own decisions")
m4=mock(); g4=guard(m4,floodguard=False); g4.apply_settings({"mode":"protect"})
g4.action("add_channel",{"name":"#trailchat","key":TRAIL}); sync(g4)
g4.action("mute",{"sender":"Lou Park","channel":"#trailchat","days":30})
before=g4.blocks[next(k for k,b in g4.blocks.items() if b["kind"]=="burst")]["expires"]
r=g4.import_decisions(json.loads(blob)); sync(g4)
check(r["added"]>=2 and r["kept"]==1,f"added the new ones, kept the one already there: {r['message']}")
check(g4.blocks[next(k for k,b in g4.blocks.items() if b["kind"]=="burst" and b["value"]=="Lou Park")]["expires"]>=before,"never shortened")
check(r["skipped"]==0,"the every-channel blocks need no particular channel")
check(act(m4,"cheap widgets for sale now","Kim Lane",["B2"],TRAIL)=="drop","the imported every-channel text block holds here")
check("Oli West" in g4.allow_senders and "net check tonight" in g4.allow_texts,"exceptions come across")
ex["blocks"].append({"kind":"burst","value":"Pat Gale","channel":"#harbour","seconds_left":3600})
r2=g4.import_decisions(ex)
check(r2["skipped"]==1 and "#harbour" in r2["message"],"a channel this one doesn't read is left out and named")
r3=g4.import_decisions(ex)
check(r3["added"]==0,"importing again adds nothing new")

# Damaged or hostile files are refused or skipped, never fatal
for junk in (None,[],{"format":"other"},{"format":"spamguard-decisions","version":9},{"format":"spamguard-decisions","version":1,"blocks":"x"}):
    try: g4.import_decisions(junk); refused=False
    except ValueError: refused=True
    check(refused,f"refused: {str(junk)[:40]}")
r=g4.import_decisions({"format":"spamguard-decisions","version":1,"blocks":[
    {"kind":"text","value":"hi","seconds_left":3600},{"kind":"lockdown","value":None,"seconds_left":3600},
    {"kind":"hop","value":"ZZ","seconds_left":3600},{"kind":"burst","value":"?","seconds_left":3600},
    {"kind":"burst","value":"Sam Low","seconds_left":-5},{"kind":"route","value":["A1"],"seconds_left":3600},
    {"kind":"imposter","value":"E7","seconds_left":3600},{"kind":"text","value":"line\nbreak spam text","seconds_left":3600}]})
check(r["bad"]==8 and r["added"]==0,"each bad entry is skipped: "+r["message"])
try: g4.import_decisions({"format":"spamguard-decisions","version":1,"blocks":[{}]*(g4.DECISIONS_MAX+1)}); big=False
except ValueError: big=True
check(big,"an oversized file is refused")
check({"block_channel"}<=sg.ACTIONS,"the new action is allowed")
ui=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
check("/decisions_export" in ui and "/decisions_import" in ui and "/block_channel" in ui,"the page has the controls")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
