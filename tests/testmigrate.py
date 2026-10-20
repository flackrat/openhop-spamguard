# One SpamGuard per repeater, and moving a normal install into openHop as a plugin. The plugin is
# installed, configured and run by openHop's own plugin manager code behind the fake openHop's plugin
# API. All names and messages are made up. Needs internet access for pip (PyPI).
import sys, os, json, time, threading, urllib.request, email
from harness import *
from pathlib import Path
from repeater.plugins.manifest import load_manifest_from_wheel
from repeater.plugins.storage import PluginStorage
from repeater.plugins.runtime import PluginRuntime, PluginState
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def owner(m): return (m.policy["policy_engine"].get("objects") or {}).get("spamguard_owner") or {}
def ours(m): return [r["name"] for r in m.policy["policy_engine"]["rules"] if r.get("name","").startswith("spamguard:")]

# ---- two copies on one repeater: the second waits ----
m=mock()
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=3000)
g1=guard(m); g1.poll_once(); g1.last_sync=0; g1.sync_pending=True; g1.poll_once()
for i in range(8): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D","E1"])
g1.poll_once(); g1.poll_once()
first=ours(m); check(first and owner(m).get("id")==g1.instance_id,"first copy holds the repeater")
g2=guard(m, state_file=os.path.join(TMP,"second.json")); g2.poll_once(); g2.last_sync=0; g2.sync_pending=True; g2.poll_once(); g2.last_verify=0; g2.poll_once()
check(g2.standby is not None and g2.instance_id!=g1.instance_id,"second copy waits")
check(ours(m)==first and owner(m).get("id")==g1.instance_id,"second copy changed nothing")
st=g2.status(); check(st["install"]["standby"] and "normal install" in st["install"]["standby"]["who"],"page says who is in charge")
m.policy["policy_engine"]["objects"]["spamguard_owner"]["ts"]-=2000   # first copy stopped long ago
g2.last_verify=0; g2.poll_once()
check(g2.standby is None and owner(m).get("id")==g2.instance_id,"second copy takes over when the first stops")
g1.last_verify=0; g1.poll_once()
check(g1.standby is not None,"first copy, back again, now waits instead of fighting")

# ---- the owner marker is refreshed every ten minutes, not five (fewer writes to the Pi's SD card) ----
check(sg.LEASE_REFRESH==600 and sg.LEASE_SECONDS-sg.LEASE_REFRESH>=300,"refresh every 10 minutes, with five minutes of slack before the marker counts as stale")
g1.last_verify=0; g1.standby=None
m.policy["policy_engine"]["objects"]["spamguard_owner"]={"id":g2.instance_id,"kind":"normal","host":"x","version":sg.VERSION,"state":"active","ts":round(time.time())-400}
p0=m.posts; g2.sync_policy(); check(m.posts==p0,"a marker 400 seconds old is left alone (no write to openHop)")
m.policy["policy_engine"]["objects"]["spamguard_owner"]["ts"]=round(time.time())-650
g2.sync_policy(); check(m.posts>p0 and time.time()-float(owner(m).get("ts"))<5,"one 650 seconds old is refreshed")
p1=m.posts; g2.sync_policy(); check(m.posts==p1,"and then left alone again")

# ---- moving a normal install into openHop as a plugin ----
sys.path.insert(0, os.path.join(REPO, "tools")); import build_plugin
wheel = build_plugin.build(os.path.join(TMP, "dist"))
storage=PluginStorage(os.path.join(TMP,"plugins")); storage.ensure_root(); rt=PluginRuntime(storage)
def plugins(h, method, path, q):
    def send(code, obj):
        b=json.dumps(obj).encode(); h.send_response(code); h.send_header("Content-Type","application/json"); h.end_headers(); h.wfile.write(b)
    try:
        if method=="GET" and path=="/api/plugins":
            return send(200,{"success":True,"plugins":[{"id":i} for i in storage.list_plugin_ids()]})
        if method=="GET" and path=="/api/plugins/runtime":
            return send(200,{"success":True,"runtime":storage.read_runtime(q["id"])})
        n=int(h.headers.get("Content-Length") or 0); raw=h.rfile.read(n)
        if path=="/api/plugins/install":
            msg=email.message_from_bytes(b"Content-Type: "+h.headers["Content-Type"].encode()+b"\r\n\r\n"+raw)
            part=[p for p in msg.walk() if p.get_param("name",header="content-disposition")=="wheel"][0]
            dest=Path(TMP)/"upload"/part.get_filename(); dest.parent.mkdir(exist_ok=True); dest.write_bytes(part.get_payload(decode=True))
            info=rt.install_wheel(dest, load_manifest_from_wheel(dest)); return send(200,{"success":True,"plugin":info})
        body=json.loads(raw or b"{}")
        if path=="/api/plugins/settings":
            storage.write_config(body["id"], body["config"]); return send(200,{"success":True})
        if path=="/api/plugins/enable":
            s=storage.read_state(body["id"]); s["enabled"]=True; storage.write_state(body["id"],s); rt.start(body["id"]); return send(200,{"success":True})
        if path=="/api/plugins/start":
            rt.start(body["id"]); return send(200,{"success":True})
        return send(404,{"success":False,"error":"not found"})
    except Exception as e:
        return send(500,{"success":False,"error":str(e)})
m=mock(); m.plugins=plugins
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=3000)
m.add("Canal Boat Ted","Anyone hearing me from the lock?",["A7","2F"],ago=2900)
port=18231
g=guard(m, listen_port=port, plugin_wheel_url=Path(wheel).as_uri(), mode="protect")
srv=sg.QuietServer(("127.0.0.1",port), sg.make_handler(g)); threading.Thread(target=srv.serve_forever,daemon=True).start()
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for i in range(8): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D","E1"])
g.poll_once(); g.poll_once()
known_before=set(g.known); rules_before=len(ours(m))
check("Hilltop Hiker" in known_before and rules_before>0,"normal install is protecting")
g._plugins_checked=0; g._maybe_check_plugins()
s=g.move_summary(); check(s["possible"],"move offered when openHop can run plugins: "+str(s))
r=g.start_move_to_plugin(); check(r["ok"],"move started")
t0=time.time()
while time.time()-t0<300 and (g.move_state or {}).get("running"): time.sleep(2)
ms=g.move_state or {}
check(ms.get("ok") is True,"move finished: "+str(ms.get("message"))[:160])
check(getattr(g,"retired",False),"old copy steps down")
data=storage.paths_for("openhop-spamguard").data_dir
imp=json.loads((data/"state.json").read_text()) if (data/"state.json").exists() else {}
check(known_before <= set(imp.get("known_senders") or {}),"plugin picked up the known people")
cfg=storage.read_config("openhop-spamguard")
check(cfg.get("api_key")=="t" and "import_from" not in cfg,"token copied, one-time link forgotten")
took=None
for _ in range(40):
    if owner(m).get("kind")=="plugin" and owner(m).get("state")=="active": took=True; break
    time.sleep(1)
check(took,"plugin takes over the repeater: "+str(owner(m)))
check(len(ours(m))>0,"rules still in place after the handover: "+str(len(ours(m))))
srv.shutdown(); srv.server_close()   # the old copy switches off and frees the port
page=None
for _ in range(30):
    try: page=json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=2).read()); break
    except Exception: time.sleep(1)
check(page and page["install"]["kind"]=="plugin","plugin's page opens on the same port once it is free")
kn=(page or {}).get("known") or {}
check(page and kn.get("count",0)+kn.get("learning",0)>=len(known_before),"plugin's page carries the regulars over: "+str(kn))
g2=guard(m, state_file=os.path.join(TMP,"again.json")); g2.poll_once(); g2.last_sync=0; g2.sync_pending=True; g2.poll_once()
check(g2.standby is not None,"a normal install started again afterwards waits for the plugin")
rt.stop("openhop-spamguard")
time.sleep(1)
check(owner(m).get("state")=="released","plugin lets go when openHop switches it off")
g2.last_verify=0; g2.poll_once()
check(g2.standby is None and owner(m).get("id")==g2.instance_id,"so switching back to a normal install is instant")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
