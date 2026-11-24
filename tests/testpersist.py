# Persistent senders, held messages and automatic updates. Checked against openHop's own rule engine.
# All names and messages are made up.
import sys, logging, time
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def sync(g): g.last_sync=0; g.sync_pending=True; g.poll_once()
def ev(sender,text,path=("A1","B2")): return sg.Event(ts=time.time(),sender=sender,text=text,path=list(path),channel="Public")
STRANGER=dict(known_min_msgs=500,known_min_minutes=100000)
def send(m,sender,text,path,ago):
    # each send carries its own send time, as a real radio's does (copies of one send share it)
    m.packets.append({"id":len(m.packets)+1,"timestamp":time.time()-ago,"type":5,
        "payload":enc(sender,text,sent=time.time()-ago),"packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})

# --- A message sent all day stays held
SLOGAN=["widgetco dot example is a fake shop, the real one is widgets dot example, the fake shop is run by Fred Bloggs, avoid",
        "widgetco dot example is a fake shop< the real one is widgets dot example. the fake shop is run by Fred Bloggs. avoid",
        "widgetco dot example is, a fake shop the real one is widgets dot example. the fake shop is run by Fred Bloggs; avoid"]
m=mock(); g=guard(m,floodguard=False,**STRANGER); g.apply_settings({"mode":"protect"}); sync(g)
for i in range(6): send(m,"LOUD SHOUTER",SLOGAN[0],["C1","D2"],ago=6800-i*300)
sync(g)
held=[b for k,b in g.blocks.items() if k.startswith("slowrepeat:")]
check(len(held)==1,"the same message all day: held")
check(m.decide("LOUD SHOUTER",SLOGAN[0],["C1","D2"])=="drop","the first wording is stopped in openHop")
for i in range(3): send(m,"LOUD SHOUTER",SLOGAN[1],["C1","D2"],ago=4800-i*300)
sync(g)
check(m.decide("LOUD SHOUTER",SLOGAN[1],["C1","D2"])=="drop","a changed copy: still stopped in openHop")
for i in range(3): send(m,"LOUD SHOUTER",SLOGAN[2],["C1","D2"],ago=2500-i*300)
sync(g)
check(m.decide("LOUD SHOUTER",SLOGAN[2],["C1","D2"])=="drop","and again after another change")
b=next(b for k,b in g.blocks.items() if k.startswith("slowrepeat:"))
check(all(g.block_matches(b,ev("LOUD SHOUTER",t)) for t in SLOGAN),"SpamGuard's own count agrees for every wording")
check(m.decide("Someone Else",SLOGAN[2],["C1","D2"])=="allow","someone else quoting it is not held by this")
check(all(len(a)>=12 and not any(ch in a for ch in ",.;<") for a in b.get("alts") or []),"the extra pieces are plain words")
check(len(b.get("alts") or [])<=g.ALTS_MAX,"and there are only a few of them")

# --- Far past the limit, after being held before: held by name, however it is written
m2=mock(); g2=guard(m2,floodguard=False,**STRANGER); g2.apply_settings({"mode":"protect"}); sync(g2)
g2.offences["LOUD SHOUTER"]=[time.time()-3000,time.time()-2000]
for i in range(9): send(m2,"LOUD SHOUTER",SLOGAN[i%3],["C1","D2"],ago=6800-i*600)
sync(g2)
pk=[b for k,b in g2.blocks.items() if k.startswith("persist:")]
check(len(pk)==1 and pk[0]["kind"]=="burst","a repeat offender far past the limit is held by name")
check(m2.decide("LOUD SHOUTER","WIDGETCO dot EXAMPLE IS A FAKE SHOP",["C1","D2"])=="drop","a changed copy doesn't help")
check(m2.decide("Quiet Person","widgetco dot example is a fake shop",["C1","D2"])=="allow","nobody else is affected")
check(pk and pk[0]["expires"]<time.time()+2*86400+60,"for a limited time")
# never for a name SpamGuard knows
m3=mock(); g3=guard(m3,floodguard=False); g3.apply_settings({"mode":"protect"}); sync(g3)
send(m3,"Ann Hill","hello all",["4C"],ago=7000); sync(g3)
g3.known["Ann Hill"][2]=50   # a regular with plenty of ordinary messages behind her
check(g3.is_known("Ann Hill"),"Ann Hill is known")
g3.offences["Ann Hill"]=[time.time()-3000,time.time()-2000]
for i in range(9): send(m3,"Ann Hill",SLOGAN[0],["4C"],ago=6800-i*600)
sync(g3)
check(not any(k.startswith("persist:") for k in g3.blocks),"a known name is never held by name this way")

# A new name that changes every copy ends up held by name
mc=mock(); gc=guard(mc,floodguard=False,**STRANGER); gc.apply_settings({"mode":"protect"}); sync(gc)
base=SLOGAN[0]
for i in range(10):
    t="".join(ch.upper() if (j+i)%(i+2)==0 else ch for j,ch in enumerate(base))
    send(mc,"CAPS CHANGER",t,["C1","D2"],ago=6800-i*600); sync(gc)
    gc.offences["CAPS CHANGER"]=[x-3700 for x in gc.offences.get("CAPS CHANGER",[])]   # an hour or so passes
check(any(k.startswith("persist:") for k in gc.blocks),"changing every copy: held by name in the end")
check(mc.decide("CAPS CHANGER","WiDgEtCo DoT eXaMpLe Is A fAkE sHoP",["C1","D2"])=="drop","whatever it sends")

# A new name whose every copy is broken up so that no plain piece survives is held by name straight away
mp=mock(); gp=guard(mp,floodguard=False,**STRANGER); gp.apply_settings({"mode":"protect"}); sync(gp)
marks=",.;:!?"
for i in range(7):
    t=" ".join(w+marks[(i+j)%6] for j,w in enumerate(SLOGAN[0].replace(",","").split()))
    send(mp,"DOT DASHER",t,["C1","D2"],ago=6800-i*600); sync(gp)
check(any(k.startswith("persist:") for k in gp.blocks),"no piece of the hold can follow it: held by name")
check(mp.decide("DOT DASHER","anything at all",["C1","D2"])=="drop","whatever it sends next")
check(mp.decide("Passer By","widgetco dot example is a fake shop",["C1","D2"])=="allow","nobody else is affected")

# --- A quick repeat that changes
m4=mock(); g4=guard(m4,floodguard=False,**STRANGER); g4.apply_settings({"mode":"protect"}); sync(g4)
Q=["buy the shiny gadget today at gadget corner, best prices in town","buy the shiny gadget today at gadget corner. best prices in town!",
   "buy the shiny gadget today at gadget corner; best prices in town?","buy the shiny gadget today at gadget corner - best prices in town",
   "buy the shiny gadget today at gadget corner: best prices in town"]
for i,t in enumerate(Q): send(m4,"Gadget Seller",t,["E5"],ago=200-i*20)
sync(g4)
check(m4.decide("Gadget Seller","buy the shiny gadget today at gadget corner... best prices in town",["E5"])=="drop","another changed copy of a quick repeat is stopped")

# --- A remembered sentence that comes back changed
m5=mock(); g5=guard(m5,floodguard=False,remember_sentences=True,**STRANGER); g5.apply_settings({"mode":"protect"}); sync(g5)
R1="Nobody here asked for your widget company to own the whole hobby"
R2="Nobody here, asked for your widget company. to own the whole hobby"
send(m5,"QX7%ZZ1A",R1,["F1","72"],ago=4000); sync(g5)
send(m5,"K2#LL0PQ",R1,["F1","04"],ago=3000); sync(g5)
check(m5.decide("NEWNAME9",R1,["F1","72"])=="drop","the sentence is held")
send(m5,"P0P0P0P9",R2,["F1","04"],ago=60); sync(g5)
check(m5.decide("OTHERNM8",R2,["F1","72"])=="drop","a changed copy of the sentence is held too")

R3="Nobody, here. asked; for: your! widget? company, to. own; the: whole! hobby"
send(m5,"Z9Z9Z9Z8",R3,["F1","04"],ago=30); sync(g5)
check(m5.decide("LASTNAM7","Nobody; here: asked! for? your, widget. company; to: own! the? whole, hobby",["A7","B8"])=="drop","broken up between every word: its longer words together are held")
wb=next(b for k,b in g5.blocks.items() if k.startswith("sentencew:"))
check(not g5.block_matches(wb,ev("LASTNAM7","Nobody asked about the whole company outing")),"sharing a few of the words is not enough")
check(g5.gated(wb),"and it sits after the known-people rule, so people SpamGuard knows get through it")

# --- A block still catching spam isn't dropped the moment its time is up
m6=mock(); g6=guard(m6,floodguard=False,**STRANGER); g6.apply_settings({"mode":"protect"}); sync(g6)
g6._add_block("hop:C1","hop","C1","test","hop",ttl=600)
b6=g6.blocks["hop:C1"]; b6["expires"]=time.time()-1; b6["last_spam"]=time.time()-300
g6._expire_blocks(time.time())
check("hop:C1" in g6.blocks and g6.blocks["hop:C1"]["expires"]>time.time()+3000,"still catching spam: kept a while longer")
b6["expires"]=time.time()-1; b6["last_spam"]=time.time()-7200
g6._expire_blocks(time.time()); check("hop:C1" not in g6.blocks,"nothing caught lately: it ends as before")
g6._add_block("hop:C2","hop","C2","test","hop",ttl=600); b7=g6.blocks["hop:C2"]
b7["created"]=time.time()-90000; b7["expires"]=time.time()-1; b7["last_spam"]=time.time()-60
g6._expire_blocks(time.time()); check("hop:C2" not in g6.blocks,"never more than a day in all")
g6._add_block("text:x","text","some manual spam text here","test","manual",ttl=600); b8=g6.blocks["text:x"]
b8["expires"]=time.time()-1; b8["last_spam"]=time.time()-60
g6._expire_blocks(time.time()); check("text:x" not in g6.blocks,"your own blocks end when you said")

# --- Saying Spam about a message a repeater block is holding also holds its words
m7=mock(); g7=guard(m7,floodguard=False,**STRANGER); g7.apply_settings({"mode":"protect"}); sync(g7)
g7._add_block("hop:C1","hop","C1","test","hop",ttl=600)
T7="the gadget corner shop is a total scam and you should stay away from it"
r=g7.give_verdict({"verdict":"spam","status":"held","sender":"AB12CD34","text":T7,"path":"C1>D2","packet":"p7","channel":"Public","matched":"hop:C1"})
check(r.get("ok") and any(b.get("source")=="manual" and b["kind"]=="text" for b in g7.blocks.values()),"its words are held as well")
check("after the block" in r["message"],"and the answer says so")
g7.give_verdict({"verdict":"none","sender":"AB12CD34","text":T7,"packet":"p7"})
check(not any(b.get("source")=="manual" and b["kind"]=="text" for b in g7.blocks.values()),"taking the answer back removes it")

# --- Disguised letters and invisible characters on Public from names it doesn't know
m8=mock(); g8=guard(m8,floodguard=False,symbol_junk=True,**STRANGER); g8.apply_settings({"mode":"protect"}); sync(g8)
check(m8.decide("NEWNAME1","buy widgеts nоw at the shop",["F1"])=="drop","a Cyrillic look-alike letter: held")
check(m8.decide("NEWNAME1","buy wid­gets now at the shop",["F1"])=="drop","an invisible soft hyphen: held")
check(m8.decide("NEWNAME1","buy widgets now at the shop",["F1"])=="allow","ordinary text: through")
check(m8.decide("NEWNAME1","café open late tonight",["F1"])=="allow","accented letters are fine")
send(m8,"Ann Hill","hello",["4C"],ago=99999); g8.allow_senders.add("Ann Hill"); sync(g8)
check(m8.decide("Ann Hill","привет everyone",["4C"])=="allow","someone it knows writing in Cyrillic: through")
check(g8.block_matches(g8.blocks["junk:symbols"],ev("NEWNAME1","nоw")),"SpamGuard's own count agrees")
g8.apply_settings({"lookalike_junk":False}); sync(g8)
check(m8.decide("NEWNAME1","buy widgеts nоw at the shop",["F1"])=="allow","the look-alike part has its own switch")
check(m8.decide("NEWNAME1","buy wid­gets now at the shop",["F1"])=="drop","invisible characters stay held")
check(sg.DEFAULT_CONFIG["lookalike_junk"] is True,"on by default")

# --- Automatic updates
check(sg.DEFAULT_CONFIG["auto_update"] is False,"automatic updates are off until you turn them on")
check("auto_update" in sg.KEEP_ON_RESET,"and a settings reset leaves your choice alone")
m9=mock(); g9=guard(m9,floodguard=False); now=time.time()
newer=".".join(str(int(x)+(1 if i==0 else 0)) for i,x in enumerate(sg.VERSION.split(".")))
sg.IN_PLUGIN_SAVE=sg.IN_PLUGIN; sg.IN_PLUGIN=True
g9.update_info={"latest":newer,"published":now-3*3600}
check(g9.auto_update_due(now) is None,"off: never installs by itself")
g9.cfg["auto_update"]=True
check(g9.auto_update_due(now)==newer,"on, and out for a while: due")
g9.update_info={"latest":newer,"published":now-600}
check(g9.auto_update_due(now) is None,"just out: waits first")
g9.update_info={"latest":newer,"seen":{"version":newer,"ts":now-3*3600}}
check(g9.auto_update_due(now)==newer,"no release date known: counts from when it was first seen")
g9.auto_update_tried={"version":newer,"ts":now-60}
check(g9.auto_update_due(now) is None,"tried a minute ago: not again yet")
g9.auto_update_tried={"version":newer,"ts":now-2*86400}
check(g9.auto_update_due(now)==newer,"tried long ago: once more")
g9.update_info={"latest":sg.VERSION,"published":now-86400}
check(g9.auto_update_due(now) is None,"already up to date: nothing")
called=[]
g9.update_info={"latest":newer,"published":now-3*3600}; g9.auto_update_tried={}
g9.update_action=lambda op,body: called.append((op,body)) or {"ok":True}
g9._maybe_auto_update()
check(called==[("install_update",{"version":newer,"auto":True})],"when due it asks for that version, once, as an automatic install")
check(g9.auto_update_tried.get("version")==newer,"and remembers it tried")
g9._maybe_auto_update(); check(len(called)==1,"not twice")
sg.IN_PLUGIN=sg.IN_PLUGIN_SAVE
check(g9.update_summary()["auto_update"] is True,"the page is told it's on")

g9.cfg["update_check"]="off"; g9.auto_update_tried={}; g9.update_info={"latest":newer,"published":now-3*3600}
sg.IN_PLUGIN=True; check(g9.auto_update_due(now) is None,"not looking for versions: automatic updates wait too"); sg.IN_PLUGIN=sg.IN_PLUGIN_SAVE
g9.cfg["update_check"]="daily"

# --- Being counted: once a day, nothing sent, and two ways to stop it
import urllib.request as _ur
asked=[]
class _R:
    def __enter__(s): return s
    def __exit__(s,*a): return False
    def read(s,n=-1): return b""
real_open=_ur.urlopen
def fake_open(req,timeout=None):
    u=req.full_url if hasattr(req,"full_url") else str(req)
    if "github.com" not in u: return real_open(req,timeout=timeout)   # the test's own mock repeaters
    asked.append((u, dict(getattr(req,"headers",{})), getattr(req,"data",None))); return _R()
sg.urllib.request.urlopen=fake_open
g9.started=time.time()-1000; g9.count_ping=0; g9.cfg["count_install"]=True; g9.cfg["update_check"]="daily"
g9._maybe_count(); time.sleep(0.3)
check(len(asked)==1 and asked[0][0].endswith("/releases/latest/download/SHA256SUMS"),"counted by one download of a release file")
check(asked[0][2] is None and set(k.lower() for k in asked[0][1])=={"user-agent"} and sg.VERSION not in str(asked[0][1]),"nothing is sent with it, not even the version")
g9._maybe_count(); time.sleep(0.2); check(len(asked)==1,"once a day at most")
g9.count_ping=time.time()-90000; g9.cfg["count_install"]=False; g9._maybe_count(); time.sleep(0.2)
check(len(asked)==1,"switched off: not counted")
g9.cfg["count_install"]=True; g9.cfg["update_check"]="off"; g9._maybe_count(); time.sleep(0.2)
check(len(asked)==1,"not looking for versions: not counted either "+str([a[0] for a in asked]))
g9.cfg["update_check"]="daily"
sg.urllib.request.urlopen=real_open
check(sg.DEFAULT_CONFIG["count_install"] is True and "count_install" in sg.KEEP_ON_RESET,"on unless you turn it off, and a reset leaves your choice")
check("identifier" in sg.META_BY_KEY["count_install"]["help"],"and the setting says plainly what it is for")

# --- A change on the page answers straight away; the rules are written by the loop, never while the lock is held
import threading
m10=mock(); g10=guard(m10,floodguard=False); g10.apply_settings({"mode":"protect"}); sync(g10)
calls=[]
real=g10.sync_policy
g10.sync_policy=lambda force=False: calls.append(force) or True
g10._loop_alive=True
t0=time.time(); g10.action("block_text",{"text":"a long enough spam message to block here","channel":"Public"})
check(not calls and time.time()-t0<1,"with the loop running, a page change doesn't wait for openHop")
check(g10.sync_pending and g10._force_sync and g10.wake.is_set(),"it asks the loop to write the rules straight away")
g10.sync_policy=real; g10._loop_alive=False
free=[]
real_api=g10._api
def spy(method,path,body=None,**k):
    if method=="POST" and path=="/api/policy":
        got=[]; th=threading.Thread(target=lambda: got.append(g10.lock.acquire(timeout=1)) or (got[0] and g10.lock.release())); th.start(); th.join()
        free.append(bool(got and got[0]))
    return real_api(method,path,body,**k) if body is not None else real_api(method,path,**k)
g10._api=spy; g10.sync_policy(force=True); g10._api=real_api
check(free==[True],"the lock is free while openHop takes the rules")
check(any("block" in str(r.get("name","")) or "text" in str(r.get("name","")) for r in m10.policy["policy_engine"]["rules"]),"and the rules arrive")
g10.sync_pending=True; seq=g10.__dict__["_sync_seq"]; g10.sync_pending=True
check(g10.__dict__["_sync_seq"]==seq+1,"each request for new rules is counted")

# --- Using the suggested level keeps Auto on; any other level turns it off
m11=mock(); g11=guard(m11,floodguard=False); g11.apply_settings({"level_auto":True}); g11.level_preview={"suggested":70}
g11.apply_settings({"level":70}); check(g11.cfg["level_auto"] is True,"the suggested level: Auto stays on")
g11.apply_settings({"level":40}); check(g11.cfg["level_auto"] is False,"a level of your own: Auto goes off, as before")

# --- Reworded spam from your marks: on by default, never for people SpamGuard knows
check(sg.DEFAULT_CONFIG["text_sense"] is True and sg.DEFAULT_CONFIG["text_sense_log_only"] is False,"on and holding by default")
m12=mock(); g12=guard(m12,floodguard=False,text_sense=True,text_sense_log_only=False)
g12.known["Ann Hill"]=[time.time()-90000,time.time(),50]
g12.sense.ready=lambda: True; g12.sense.score=lambda t: 99; g12.sense.line=lambda: 1
e1=ev("Ann Hill","this reads exactly like the spam you marked before"); e1.packet="k1"; g12._sense_note(e1)
e2=ev("STRANGR9","this reads exactly like the spam you marked before"); e2.packet="k2"; g12._sense_note(e2)
check(not any(k.startswith("Ann Hill|") for k in g12.sense_sends),"someone it knows is never counted")
check(any(k.startswith("STRANGR9|") for k in g12.sense_sends),"a stranger is")

# --- People: a name held for spam says so, with the evidence, instead of "Learning"
row=lambda gg,n: next(r for r in gg.people({"show":"all","q":n})["rows"] if r["name"]==n)
r2=row(g2,"LOUD SHOUTER")
check(r2["standing"]=="held" and r2["why"].startswith("Held for sending spam"),"a name held for spam is shown as Held: "+r2["why"])
check(r2["spam"] and r2["spam"]["holds"] and r2["spam"]["until"],"with what is holding it now and until when")
check(g2.people({"show":"held"})["counts"]["held"]==1 and g2.people({"show":"learning"})["counts"]["learning"]==0,"it has its own list, and isn't under Learning")
check("LOUD SHOUTER" in [r["name"] for r in g2.people({"show":"active"})["rows"]],"and is on the first list you see")
rc=row(gc,"CAPS CHANGER")
check(rc["spam"]["dodges"]>=1 and "changed how it is written" in rc["why"],"getting round a hold is counted and said: "+rc["why"])
ra=row(g3,"Ann Hill"); check(ra["standing"]!="held" and ra["spam"] is None,"someone who earned the known pass is never shown as Held")
q=mock(); gq=guard(q,floodguard=False,**STRANGER); gq.apply_settings({"mode":"protect"}); sync(gq)
send(q,"New Walker","anyone about on the ridge this morning",["C4"],ago=300); sync(gq)
check(row(gq,"New Walker")["standing"]=="learning","an ordinary newcomer is still Learning")
gq.name_links["Second Name"]={"after":["First Name"],"ts":time.time()}
check(gq.spam_record("Second Name")["linked"]==["First Name"] and gq.spam_record("First Name")["linked"]==["Second Name"],"names that carried on one message are linked both ways")
# Trusting a name ends SpamGuard's own holds on it
check(any(k.startswith("persist:") for k in g2.blocks),"(held by name)")
g2.action("allow_sender",{"sender":"LOUD SHOUTER"})
check(not any(k.startswith("persist:") or k.startswith("slowrepeat:") for k in g2.blocks),"Trust ends SpamGuard's own holds on that name")
check(row(g2,"LOUD SHOUTER")["standing"]=="trusted","and it is shown as trusted")

# --- 6.42.0: near-copies, short repeats, the known pass, packed text, rule allowance
import random
random.seed(11)
FILL="lol hey ok so right well yes btw fyi hmm listen folks today again still really".split()
def series(gg,mm,who,gen,n=12,gap=560,path=("C1","D2")):
    out=[]
    for i in range(n):
        t=gen(i); out.append(mm.decide(who,t,list(path))=="drop"); send(mm,who,t,list(path),ago=6900-i*gap); sync(gg)
    return out
def new(**kw):
    mm=mock(); gg=guard(mm,floodguard=False,**dict(STRANGER,**kw)); gg.apply_settings({"mode":"protect"}); sync(gg); return mm,gg
PLAIN=SLOGAN[0].replace(",","")
ma,ga=new(); oa=series(ga,ma,"Filler Adder",lambda i:(lambda ws,k:" ".join(ws[:k]+[random.choice(FILL)]+ws[k:]))(PLAIN.split(),random.randrange(18)))
check(sum(oa)>=5 and len([k for k in ga.slow_sends if k.startswith("Filler Adder|") and "|S" not in k])==1,f"a word added somewhere each time is still the same message ({sum(oa)} of 12 stopped)")
mb,gb=new(); ob=series(gb,mb,"Word Swapper",lambda i:(lambda ws,a,b:" ".join(ws[b] if j==a else ws[a] if j==b else w for j,w in enumerate(ws)))(PLAIN.split(),random.randrange(18),random.randrange(18)))
check(sum(ob)>=5,f"so is one with words moved about ({sum(ob)} of 12)")
check(any(k.startswith("persist:") for k in gb.blocks),"and a hold that has had to follow the wording twice becomes a hold on the name")
mk,gk=new(); okk=series(gk,mk,"Number Adder",lambda i:PLAIN+" "+str(random.randrange(10,99)))
check(sum(okk)>=6,f"a different number on the end each time ({sum(okk)} of 12)")
# different messages from one name are not lumped together
md,gd=new()
for i,t in enumerate(["the repeater on the hill is back up after the storm last night","anyone know a good antenna for a narrowboat please asking for a friend",
                      "thanks to everyone who helped with the range test on saturday it went well","we are meeting at the village hall on thursday if anyone wants to come"]*2):
    send(md,"Chatty Newcomer",t+(" again" if i>3 else ""),["C4"],ago=6900-i*600); sync(gd)
check(not any(k.startswith(("slowrepeat:","persist:")) for k in gd.blocks),"four different messages, each said twice, are not one repeated message")
# range-test replies and readings, where the numbers are the message, are left alone on test and other channels
mw,gw=new()
def evc(ch,who,text):
    x=ev(who,text); x.channel=ch; return x
first=evc("#test","Hill Bot","I hear you loud and clear from the station on the hill tonight. 6 hops away at 06:42"); gw._note_slow_send(first)
again=evc("#test","Hill Bot","I hear you loud and clear from the station on the hill tonight. 9 hops away at 07:15"); again.ts=first.ts+900
check(gw._slow_near(again,sorted(set(sg.normalise(again.text).split()))) is None,"on a test channel, replies that differ in their numbers are separate messages")
p1=evc("Public","Hill Bot","I hear you loud and clear from the station on the hill tonight. 6 hops away at 06:42"); gw._note_slow_send(p1)
p2=evc("Public","Hill Bot","I hear you loud and clear from the station on the hill tonight. 9 hops away at 07:15"); p2.ts=p1.ts+900
check(gw._slow_near(p2,sorted(set(sg.normalise(p2.text).split()))) is not None,"on Public they count as the same message")
# short messages
ms,gs=new(); osh=series(gs,ms,"Short Shouter",lambda i:"WIDGETCO IS A FRAUD",n=30,gap=230)
check(sum(osh)>=18 and not any(osh[:8]),f"a short message repeated all day is held, after more copies than a long one ({sum(osh)} of 30)")
mg,gg2=new()
for i in range(6): send(mg,"Polite Newcomer","good morning all",["C4"],ago=6900-i*1100); sync(gg2)
check(not any(k.startswith(("slowrepeat:","persist:")) for k in gg2.blocks),"a greeting said six times in a day is fine")
for i in range(12): send(mg,"One Worder","test",["C4"],ago=6000-i*300); sync(gg2)
check(not any(b.get("who")=="One Worder" or b.get("value")=="One Worder" for b in gg2.blocks.values()),"a single word is never counted this way")
# repeating a message can't earn the known pass
mr,gr=new(known_min_msgs=3,known_min_minutes=60)
orr=series(gr,mr,"Pass Farmer",lambda i:" ".join(w+",.;:"[(i+j)%4] for j,w in enumerate(PLAIN.split())))
check(not gr.earned_known("Pass Farmer"),"copies of a repeated message don't count towards the known pass")
check(any(k.startswith("persist:") for k in gr.blocks) and sum(orr)>=6,f"so the name is held ({sum(orr)} of 12)")
# someone SpamGuard knows well is never held by name for it, only the repeated text is
mz,gz=new(known_min_msgs=3,known_min_minutes=60)
gz.known["Old Regular"]=[time.time()-30*86400,time.time()-8000,400]
oz=series(gz,mz,"Old Regular",lambda i:" ".join(w+",.;:"[(i+j)%4] for j,w in enumerate(PLAIN.split())))
check(not any(b["kind"] in ("burst","imposter") for b in gz.blocks.values()),"a well-known name is never held by name for repeating")
check(mz.decide("Old Regular","evening all, back from the hill",["C1","D2"])=="allow","anything else they say gets through")
# a name with only a few ordinary messages behind it hasn't earned that yet
my,gy=new(known_min_msgs=3,known_min_minutes=60)
gy.known["Quick Sleeper"]=[time.time()-2*86400,time.time()-8000,4]
oy=series(gy,my,"Quick Sleeper",lambda i:" ".join(w+",.;:"[(i+j)%4] for j,w in enumerate(PLAIN.split())))
check(any(b["kind"]=="imposter" and b.get("who")=="Quick Sleeper" for b in gy.blocks.values()) and sum(oy)>=6,f"a name only just known, then the same thing all day, is held through the way those copies came ({sum(oy)} of 12)")
check(my.decide("Quick Sleeper","evening all",["4C","D2"])=="allow","and still gets through any other way")
# packed text: experimental, off by default
check(sg.DEFAULT_CONFIG["packed_text_junk"] is False and sg.META_BY_KEY["packed_text_junk"]["group"]=="Experimental","packed-text hold is experimental and off")
mp2,gp2=new(symbol_junk=True)
check(mp2.decide("NEWNAME1","mct:Ab3xYz9+/qqqqqqqqqqqqqqqqq",["F1"])=="allow","off: nothing held")
gp2.apply_settings({"packed_text_junk":True}); sync(gp2)
check(mp2.decide("NEWNAME1","mct:Ab3xYz9+/qqqqqqqqqqqqqqqqq",["F1"])=="drop","on: held from a name it doesn't know")
gp2.allow_senders.add("Ann Hill"); sync(gp2)
check(mp2.decide("Ann Hill","mcmp3:Ab3xYz9+/qqqqqqqqqqqqqq",["4C"])=="allow","someone it knows gets through")
# when rules are short, each hold keeps one extra piece
mt,gt=new()
for j in range(70):
    gt._add_block(f"slowrepeat:t{j}","repeat",f"first piece of message number {j} here","test","slowrepeat",extra={"who":f"Name {j}","alts":[f"second piece number {j} goes here",f"third piece number {j} goes here",f"fourth piece number {j} goes here"]})
sync(gt); nr=len(mt.policy["policy_engine"]["rules"])
check(gt._rules_tight and nr<=70*2+60,f"many holds at once: each keeps its newest extra piece only ({nr} rules)")
b0=gt.blocks["slowrepeat:t0"]
check(gt.block_texts(b0)==[b0["value"],b0["alts"][-1]] and mt.decide("Name 0","the fourth piece number 0 goes here ok",["C1"])=="drop" and mt.decide("Name 0","second piece number 0 goes here",["C1"])=="allow","and SpamGuard's own count agrees with openHop")

print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
