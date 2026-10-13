# Running as an openHop plugin day to day: one-press updates through openHop's own plugin manager,
# Health advice that fits the install, the hang watchdog, and a clear message when openHop's plugin
# manager isn't running. All data is made up. Needs internet access for pip (PyPI).
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

# ---- Health advice per install type ----
m=mock(); g=guard(m)
check("Apply openHop fix" in (sg.fix_hint("rule") or "") and "tune-openhop.sh" in sg.fix_hint("speed"),"normal install: button and script")
sg.IN_PLUGIN=True
check("raw.githubusercontent.com" in (sg.fix_hint("rule") or "") and "--rulefix" in sg.fix_hint("rule"),"plugin: one command fetched from GitHub")
check(g.health()["can_apply_fix"] is False,"plugin: no Apply button")
try: g.request_openhop_fix(); check(False,"plugin: Apply refused")
except ValueError as e: check("curl" in str(e),"plugin: Apply explains the command instead")
check(not any("restart-on-hang" in w for w in g.health()["warnings"]),"plugin: no installer watchdog warning")
sg.IN_PLUGIN=False
# ---- watchdog ----
exited=[]; real=os._exit; os._exit=lambda c: exited.append(c)
g.loop_beat=time.time()-1000; stop=threading.Event()
th=threading.Thread(target=g.watchdog_loop,args=(stop,),kwargs={"limit":5},daemon=True)
orig_wait=stop.wait; stop.wait=lambda t: (orig_wait(0.2) or bool(exited))
th.start(); th.join(5); os._exit=real
check(exited==[70],"a stalled loop makes SpamGuard exit so it is restarted: "+str(exited))
# ---- plugin manager not running ----
def down(h, method, path, q):
    h.send_response(503); h.send_header("Content-Type","application/json"); h.end_headers()
    h.wfile.write(b'{"success":false,"error":"Plugin manager unavailable"}')
m.plugins=down; g._plugins_checked=0; g._maybe_check_plugins()
w=g.move_summary()["why_not"] or ""
check("plugin manager isn't running" in w and "openhop-plugin-manager" in w,"clear message when the plugin manager is down: "+w[:60])

# ---- one-press update of the plugin through openHop ----
sys.path.insert(0, os.path.join(REPO, "tools")); import build_plugin
d=os.path.join(TMP,"dist"); old=build_plugin.build(d)
os.environ["SPAMGUARD_BUILD_VERSION"]="5.22.1"; new=build_plugin.build(d); del os.environ["SPAMGUARD_BUILD_VERSION"]
storage=PluginStorage(os.path.join(TMP,"plugins")); storage.ensure_root(); rt=PluginRuntime(storage)
def plugins(h, method, path, q):
    def send(code,obj):
        b=json.dumps(obj).encode(); h.send_response(code); h.send_header("Content-Type","application/json"); h.end_headers(); h.wfile.write(b)
    try:
        n=int(h.headers.get("Content-Length") or 0); raw=h.rfile.read(n) if method=="POST" else b""
        if path=="/api/plugins": return send(200,{"success":True,"plugins":[{"id":i} for i in storage.list_plugin_ids()]})
        if path=="/api/plugins/install":
            msg=email.message_from_bytes(b"Content-Type: "+h.headers["Content-Type"].encode()+b"\r\n\r\n"+raw)
            part=[p for p in msg.walk() if p.get_param("name",header="content-disposition")=="wheel"][0]
            dest=Path(TMP)/"up"/part.get_filename(); dest.parent.mkdir(exist_ok=True); dest.write_bytes(part.get_payload(decode=True))
            rt.install_wheel(dest, load_manifest_from_wheel(dest)); return send(200,{"success":True})
        if path=="/api/plugins/restart":
            send(200,{"success":True}); threading.Thread(target=rt.restart,args=(json.loads(raw)["id"],),daemon=True).start(); return
        return send(404,{"success":False})
    except Exception as e: return send(500,{"success":False,"error":str(e)})
m2=mock(); m2.plugins=plugins
man=load_manifest_from_wheel(old); rt.install_wheel(old, man)
port=18241
cfg=storage.read_config(man.id); cfg.update({"api_key":"t","openhop_url":f"http://127.0.0.1:{m2.srv.server_address[1]}","listen_port":port,
    "plugin_wheel_url":Path(d).as_uri()+"/{name}"}); storage.write_config(man.id,cfg)
s=storage.read_state(man.id); s["enabled"]=True; storage.write_state(man.id,s); rt.start(man.id)
def status():
    try: return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=3).read())
    except Exception: return None
for _ in range(40):
    st=status()
    if st: break
    time.sleep(0.5)
check(st and st["update"]["installer_ready"] and not st["update"]["managed_update"],"plugin offers its own Update button")
pid0=rt._handles[man.id].process.pid
req=urllib.request.Request(f"http://127.0.0.1:{port}/install_update",data=json.dumps({"version":"5.22.1"}).encode(),method="POST",headers={"Content-Type":"application/json"})
res=json.loads(urllib.request.urlopen(req,timeout=10).read()); check(res.get("ok"),"update accepted: "+str(res)[:80])
t0=time.time()
while time.time()-t0<300 and storage.current_version(man.id)!="5.22.1": time.sleep(2)
check(storage.current_version(man.id)=="5.22.1","openHop installed the new version")
up=None
for _ in range(90):
    h=rt._handles.get(man.id)
    if h and h.process.pid!=pid0 and status(): up=True; break
    time.sleep(1)
check(up,"SpamGuard restarted on the new version and its page is back")
check((storage.paths_for(man.id).data_dir/"state.json").exists(),"what it had learnt is still there")
rt.stop(man.id)
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
