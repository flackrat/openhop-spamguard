# The protection level: a 0-100 slider that slides smoothly between the old relaxed, balanced and strict
# presets (tougher also means for longer), keeps values you set yourself unless you say otherwise, and a
# daily replay of the evidence log that shows what each level would have held. All names and messages
# here are made up.
import sys, json, logging, os, subprocess, tempfile, time, random
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

# --- the scale itself
P=sg.PRESETS
check(sg.level_values(0)==P["relaxed"] and sg.level_values(50)==P["balanced"] and sg.level_values(100)==P["strict"],
      "0, 50 and 100 are exactly the old relaxed, balanced and strict")
for k in ("repeat_block_seconds","slow_repeat_window_seconds","block_ttl_seconds"):
    check(P["relaxed"][k] < P["balanced"][k] < P["strict"][k], f"tougher also means for longer: {k}")
    check(sg.META_BY_KEY[k].get("preset"), f"{k} is set by the level (starred)")
v25, v75 = sg.level_values(25), sg.level_values(75)
check(all(min(P["relaxed"][k],P["balanced"][k]) <= v25[k] <= max(P["relaxed"][k],P["balanced"][k]) for k in v25),
      "a level between two presets gives values between theirs")
check(v75["repeat_block_seconds"]==5400 and v75["slow_repeat_window_seconds"]==108000, f"halfway is halfway: {v75}")
mono=[sg.level_values(x)["slow_repeat_hold_seconds"] for x in range(0,101)]
check(all(a<=b for a,b in zip(mono,mono[1:])), "moving up the scale never makes a hold shorter")
check([sg.level_name(x) for x in (0,19,20,50,60,79,80,100)]==["Gentle","Gentle","Easy-going","Balanced","Firm","Firm","Tough","Tough"],
      "the five names along the scale")

# --- settings from the page
m=mock(); g=guard(m)
check(g.cfg["level"]==50 and g.cfg["sensitivity"]=="balanced", "a new install starts at 50 (balanced)")
g.apply_settings({"level":80})
check(g.cfg["level"]==80 and g.cfg["slow_repeat_max"]==sg.level_values(80)["slow_repeat_max"], "choosing a level sets its values")
check(g.cfg["sensitivity"]=="strict", "older readers still see the nearest of the three presets")
for bad in (-1,101,"loud",None):
    try: g.apply_settings({"level":bad}); check(False,f"level {bad!r} should be refused")
    except ValueError: check(True,"")
g.apply_settings({"sensitivity":"relaxed"})
check(g.cfg["level"]==0 and g.cfg["hop_new_senders"]==10, "the old sensitivity choice still works and means level 0")
# your own values
g.apply_settings({"level":50}); g.apply_settings({"slow_repeat_max":2})
own=g.own_level_values()
check([o["key"] for o in own]==["slow_repeat_max"] and own[0]["yours"]==2 and own[0]["level"]==3, f"your own value is noticed: {own}")
g.apply_settings({"level":60})
check(g.cfg["slow_repeat_max"]==2 and g.cfg["level"]==60, "moving the level keeps your own value unless you say otherwise")
g.apply_settings({"level":70,"replace_own":True})
check(g.cfg["slow_repeat_max"]==sg.level_values(70)["slow_repeat_max"] and not g.own_level_values(), "or replaces it when you say so")
st=g.status()
check(st["level"]["value"]==70 and st["level"]["name"]=="Firm" and "preview" in st["level"], "the page is told the level")
check("level" in g.current_profile() and g.current_profile()["level"]==70, "a saved profile holds the level")
# it survives a restart, and an old saved 'strict' becomes 100
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg)); check(g2.cfg["level"]==70, "the level survives a restart")
m3=mock(); g3=guard(m3, sensitivity="strict"); check(g3.cfg["level"]==100, "a config file saying strict means level 100")
# profiles: an old profile with only a sensitivity, and a new one with a level
p_old=sg.SpamGuard.check_profile({"format":"spamguard-profile","version":1,"sensitivity":"relaxed","values":{}})
check(p_old["level"]==0, "an old profile's sensitivity becomes its level")
g.apply_profile({"format":"spamguard-profile","version":1,"sensitivity":"balanced","level":35,"values":{}})
check(g.cfg["level"]==35, "a profile's level is put back")
try: sg.SpamGuard.check_profile({"sensitivity":"balanced","level":150,"values":{}}); check(False,"a profile level over 100 is refused")
except ValueError: check(True,"")

# --- what each level would have held: a made-up evidence log
random.seed(3)
now=time.time(); t0=now-16*3600
# everyday chatter: every message different, as real conversation is
WORDS=("morning evening clear skies ridge lock canal base radio check loud copy heading back thanks net tonight lovely "
       "weather antenna battery solar hilltop harbour bridge road coffee walk dog signal battery mast village pub train "
       "bus rain wind sunny cloudy frost early late quiet busy").split()
people=["Hilltop Hiker","Canal Boat Ted","Base Camp 3","Sparky Sue","Quarry Pete","Lighthouse Lou"]
rows=[]
for i in range(240):
    words=random.sample(WORDS,7)
    rows.append({"type":"msg","ts":t0+i*230+random.random()*30,"sender":random.choice(people),"text":" ".join(words).capitalize(),
                 "channel":"Public","path":["A7","2F"],"packet":f"c{i}","known_then":True})
for i in range(24):   # one made-up name posting the same advert every 40 minutes
    rows.append({"type":"msg","ts":t0+600+i*2400,"sender":"Bargain Barry","text":"Cheap radios at the car boot sale this Sunday morning, come early",
                 "channel":"Public","path":["C4","9D"],"packet":f"b{i}","known_then":False})
rows.append({"type":"label","ts":now-60,"label":"spam","packet":"b20","sender":"Bargain Barry","text":"x"})
rows.sort(key=lambda r:r["ts"])
d=tempfile.mkdtemp(prefix="sg-level-test-")
day=time.strftime("%Y-%m-%d",time.localtime(now))
logf=os.path.join(d,day+".jsonl")
with open(logf,"w") as f:
    f.write("".join(json.dumps(r)+"\n" for r in rows))
here=os.path.dirname(os.path.abspath(__file__))
r=subprocess.run([sys.executable,os.path.join(here,"..","replay.py"),"--levels","0,50,100","--json",logf],capture_output=True,text=True,timeout=300)
rep=json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode==0 else {}
lv={x["level"]:x for x in rep.get("levels",[])}
check(set(lv)=={0,50,100}, f"the replay reports each level asked for: {r.stderr[-300:]}")
if lv:
    check(lv[0]["repeats"] < lv[50]["repeats"] <= lv[100]["repeats"], f"tougher levels hold more of the repeated advert: {[lv[k]['repeats'] for k in (0,50,100)]}")
    check(all(x["check"]==0 and x["wrong"]==0 for x in lv.values()), "nobody chatting normally is held at any level")
    check(rep["labelled_spam"]==1 and lv[100]["spam"]==1, "your spam label is counted")
    check(rep["messages"]==264, "every message in the log is replayed")
    check(sg.suggest_level(rep) in (50,100), f"a level is suggested from what it held: {sg.suggest_level(rep)}")
# too little traffic: no suggestion
check(sg.suggest_level({"messages":50,"from":0,"to":86400,"levels":[{"level":0,"spam":0,"repeats":3,"check":0,"wrong":0}]}) is None,
      "no suggestion from too little traffic")
check(sg.suggest_level({"messages":500,"from":0,"to":86400,"levels":[{"level":0,"spam":0,"repeats":0,"check":0,"wrong":0}]}) is None,
      "no suggestion when nothing like spam was seen")
check(sg.suggest_level({"messages":500,"from":0,"to":86400,"levels":[{"level":0,"spam":0,"repeats":5,"check":0,"wrong":0},
      {"level":50,"spam":0,"repeats":8,"check":0,"wrong":2}]})==0, "a level that would hold messages you marked as fine is avoided")

# --- the daily run inside SpamGuard (in the background, never touching openHop)
m4=mock(); g4=guard(m4, evidence_log=True, evidence_dir=d)
check(g4.preview_summary()["enabled"] and not g4.preview_summary().get("levels"), "nothing to show before the first run")
g4.refresh_level_preview()   # not due yet: waits ten minutes after starting
check(not g4._preview_busy, "it doesn't start straight away after a restart")
g4.refresh_level_preview(force=True)
for _ in range(600):
    if not g4._preview_busy: break
    time.sleep(0.5)
ps=g4.preview_summary()
check(ps.get("levels") and [x["level"] for x in ps["levels"]]==list(sg.PREVIEW_LEVELS), f"every level is worked out: {ps}")
check(ps.get("ran") and ps.get("error") is None, "and when")
try: g4.action("preview_now",{}); check(False,"asking again straight away is refused")
except ValueError as e: check("10 minutes" in str(e), f"asking again straight away is refused: {e}")
check(not [f for f in os.listdir(tempfile.gettempdir()) if f.startswith("sg-preview-")], "it tidies up after itself")
g4._save_state(force=True)
g5=sg.SpamGuard(dict(g4.file_cfg)); check((g5.preview_summary().get("levels") or [])==ps["levels"], "the result survives a restart")
m6=mock(); g6=guard(m6, evidence_log=False)
try: g6.action("preview_now",{}); check(False,"needs the evidence log")
except ValueError as e: check("evidence log" in str(e), "it needs the evidence log, and says so")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
