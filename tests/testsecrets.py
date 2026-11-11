# Secrets never leave SpamGuard: the openHop API token, the page's access key and the channel keys are not
# in the status the page reads, the rule list or the rule summary. With an access key set, reading needs it
# too; without one, only home-network host names are answered. Changes without the access key, or not sent
# as JSON, are refused. All values are made up.
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
def get(path,headers=None):
    try:
        r=urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{path}",headers=headers or {}),timeout=10)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, ""
for path in ("/status","/rules"):
    check(get(path)[0]==401,f"{path} without the access key is refused")
code,r=get("/status",{"X-API-Key":"MADEUP-PAGE-KEY-0002"})
check(code==200 and "MADEUP-OPENHOP-TOKEN" not in r and "MADEUP-PAGE-KEY" not in r,"the status over the network holds no secrets")
g.extra_channels={"#private":"0123456789abcdef0123456789abcdef"}; g.rebuild_cfg()
g._add_block("text:demo","text","widgets for sale","test","manual",channel="#private",ttl=600)
code,r=get("/rules",{"X-API-Key":"MADEUP-PAGE-KEY-0002"})
check(code==200 and "0123456789abcdef0123456789abcdef" not in r and "key#" in r,"the rule list never shows a channel key")
check(get("/health")[0] in (200,503),"health stays readable for monitoring")
try:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/evidence",timeout=10); check(False,"evidence download needs the key")
except urllib.error.HTTPError as e:
    check(e.code==401,"the evidence download needs the access key")
srv.shutdown()

# Without an access key, a page served under someone else's domain name gets nothing
g2=guard(mock())
srv2=sg.QuietServer(("127.0.0.1",0),sg.make_handler(g2)); p2=srv2.server_address[1]
threading.Thread(target=srv2.serve_forever,daemon=True).start()
def get2(host):
    try: return urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{p2}/status",headers={"Host":host}),timeout=10).status
    except urllib.error.HTTPError as e: return e.code
check(get2("attacker.example.com")==403,"a foreign host name is refused")
for h in ("127.0.0.1:8091","192.0.2.10:8091","[::1]:8091","raspberrypi:8091","raspberrypi.local","localhost"):
    check(get2(h)==200,f"a home-network name is answered ({h})")
g2.cfg["allowed_hosts"]=["spamguard.example.org"]
check(get2("spamguard.example.org")==200,"a name in allowed_hosts is answered")
srv2.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
