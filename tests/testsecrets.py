# Secrets never leave SpamGuard: the openHop API token, the page's access key and the channel keys are not
# in the status the page reads (which anyone on the network can fetch), the rule list or the rule summary.
# Changes without the access key, or not sent as JSON, are refused. All values are made up.
import json, logging, sys, urllib.request, urllib.error, threading, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

m=mock(); g=guard(m, listen_api_key="MADEUP-PAGE-KEY-0002")
g.cfg["api_key"]="MADEUP-OPENHOP-TOKEN-0001"
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
keys=[k for k in (g.cfg.get("channels") or {}).values() if isinstance(k,str) and len(k)>=16]
blob=json.dumps(g.status())+json.dumps(g.status().get("rule_summary"))
for name,secret in (("openHop API token","MADEUP-OPENHOP-TOKEN-0001"),("page access key","MADEUP-PAGE-KEY-0002")):
    check(secret not in blob,f"the {name} is not in the status")
check(keys and not any(k in blob for k in keys),"no channel key is in the status")

# The web server: changes need the access key and must be JSON
srv=sg.QuietServer(("127.0.0.1",0),sg.make_handler(g)); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
def post(headers,body=b'{"mode":"monitor"}'):
    req=urllib.request.Request(f"http://127.0.0.1:{port}/settings",data=body,method="POST",headers=headers)
    try: return urllib.request.urlopen(req,timeout=10).status
    except urllib.error.HTTPError as e: return e.code
check(post({"Content-Type":"application/json"})==401,"a change without the access key is refused")
check(post({"Content-Type":"text/plain","X-API-Key":"MADEUP-PAGE-KEY-0002"})==415,"a change not sent as JSON is refused")
check(post({"Content-Type":"application/json","X-API-Key":"MADEUP-PAGE-KEY-0002"})==200,"a proper change is accepted")
r=urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=10).read().decode()
check("MADEUP-OPENHOP-TOKEN" not in r and "MADEUP-PAGE-KEY" not in r,"the status over the network holds no secrets")
try:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/evidence",timeout=10); check(False,"evidence download needs the key")
except urllib.error.HTTPError as e:
    check(e.code==401,"the evidence download needs the access key")
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
