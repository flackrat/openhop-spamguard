# Docker mode: settings from environment variables, data in the mounted folder, and updates by
# pulling a new image instead of the Update button. All values are made up.
import sys, os, json
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
env={"OPENHOP_API_KEY":"tok123","OPENHOP_URL":"http://openhop:8000","SPAMGUARD_MODE":"protect","SPAMGUARD_SENSITIVITY":"strict",
     "SPAMGUARD_CHANNELS":"#trailchat, #test","SPAMGUARD_PASSWORD":"pw","SPAMGUARD_DATA":"/data"}
old={k:os.environ.get(k) for k in env}; os.environ.update(env)
c=sg.load_config(None)
check(c["api_key"]=="tok123" and c["openhop_url"]=="http://openhop:8000","token and address from environment")
check(c["mode"]=="protect" and c["sensitivity"]=="strict","mode and sensitivity from environment")
check(c["hashtag_channels"]==["#trailchat","#test"],"channels from environment: "+str(c.get("hashtag_channels")))
check(c["listen_api_key"]=="pw","page password from environment")
check(c["state_file"]=="/data/state.json" and c["evidence_dir"]=="/data/evidence","data kept in the mounted folder")
cf=os.path.join(TMP,"cfg.yaml"); open(cf,"w").write("mode: monitor\napi_key: fromfile\n")
c=sg.load_config(cf)
check(c["mode"]=="monitor","config file wins over the environment for settings")
check(c["api_key"]=="tok123","environment token wins (it is the safer place for it)")
for k,v in old.items():
    if v is None: os.environ.pop(k,None)
    else: os.environ[k]=v
m=mock(); g=guard(m)
sg.IN_DOCKER=True
s=g.update_summary(); check(s["docker"] is True and "docker compose pull" in s["docker_update"],"page told it runs in Docker")
try: g.update_action("install_update",{"version":"9.9"}); check(False,"Update button refused in Docker")
except ValueError as e: check("docker compose pull" in str(e),"Update explains how to update in Docker: "+str(e)[:60])
# Moving a container to the plugin: the plugin (inside openHop's container) must be able to reach this one
g.cfg["openhop_url"]="http://127.0.0.1:8000"
check(g._address_seen_by_openhop()=="127.0.0.1","next to a native openHop the handover link uses 127.0.0.1")
import socket
g.cfg["openhop_url"]="http://"+socket.gethostname()+":8000"
a=g._address_seen_by_openhop(); check(a and a.count(".")==3,"container handover address is an IPv4 address: "+str(a))
# A failed plugin check (openHop still starting) is retried within a minute, not ten
g._plugins_checked=0; g.cfg["openhop_url"]="http://127.0.0.1:1"
real=g._api
def boom(*a,**k): raise OSError("Connection refused")
g._api=boom; g._maybe_check_plugins(); g._api=real
check(g._plugins_checked < sg.time.time()-500,"failed plugin check retried soon")
check("isn't answering yet" in (g.move_summary()["why_not"] or ""),"friendly message while openHop starts: "+str(g.move_summary()["why_not"])[:60])
# Every file the Dockerfile copies in must be let through by .dockerignore (the build failed once because one wasn't).
import re
_root=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..")
_allowed={l[1:].strip() for l in open(os.path.join(_root,".dockerignore")).read().splitlines() if l.startswith("!")}
for _m in re.finditer(r"^COPY\s+(.+?)\s+\S+\s*$", open(os.path.join(_root,"Dockerfile")).read(), re.M):
    for _f in _m.group(1).split():
        check(_f in _allowed, "the Docker build can see "+_f)
sg.IN_DOCKER=False
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
