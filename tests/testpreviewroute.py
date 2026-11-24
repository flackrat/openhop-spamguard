# The level preview's replay runs with your automatic route blocks setting, and the page says when they are
# included. Made-up names and routes.
import sys, os, logging, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from harness import *
import replay
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
random.seed(4)
t0=1_790_000_000
msgs=[]
for i in range(30):   # regulars on other routes
    msgs.append({"ts":t0+i*120,"sender":f"Regular {i%6}","text":f"Evening chat line {i} about the weather","path":["1A","2B"],"channel":"Public","packet":f"p{i}"})
for i in range(14):   # a burst of new names down one route
    msgs.append({"ts":t0+4000+i*20,"sender":random.choice(["Ash","Bryn","Cole","Dale","Eden","Fern","Gale","Hart","Ivy","Jude","Kerr","Lark","Moss","Nell"])+" "+random.choice(["Mobile","Home","Base","Walker"])+f" {i}","text":random.choice(["hi all","anyone about","morning","test test","who is on","hello mesh","good evening","nice day","checking in","radio check","first time here","hey","signal ok?","yo"])+f" {i}","path":["7D","8E","9F"],"channel":"Public","packet":f"s{i}"})
msgs.sort(key=lambda m:m["ts"])
res={}
for ra in (True,False):
    caught,_g=replay.run(msgs,{"route_auto":ra},{},quiet_step=60)
    res[ra]=(_g.cfg.get("route_auto"), sum(1 for k,s2 in caught.values() if k))
check(res[True][0] is True and res[False][0] is False,"the replay runs with route_auto as given: %s"%res)
check(res[True][1]>=res[False][1],"and holds at least as much with it on: %s"%res)
# the preview hands your route_auto (and the other non-level settings) to the replay
g=guard(mock(), route_auto=True)
check("route_auto" in sg.profile_keys() and "route_auto" not in sg.PRESETS["balanced"],"route_auto goes to the preview with your other settings")
check(g.preview_summary()["route_auto"] is True,"and the page is told it's included")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
