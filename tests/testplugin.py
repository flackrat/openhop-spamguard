# SpamGuard as an openHop plugin, installed, configured, started and stopped by openHop's own plugin
# manager code, against a fake openHop with made-up traffic. Needs internet access for pip (PyPI).
import sys, os, json, time, signal, urllib.request, subprocess
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
sys.path.insert(0, os.path.join(REPO, "tools")); import build_plugin
wheel = build_plugin.build(os.path.join(TMP, "dist"))
man = load_manifest_from_wheel(wheel)
check(man.id=="openhop-spamguard" and man.runtime, "openHop accepts the manifest")
check(man.ui is not None and man.ui.entry=="spamguard-ui/index.html", "doorway page for openHop's Open button")
check(man.version==build_plugin.version(), "manifest version matches SpamGuard's")
import zipfile
_req=[l.split(":",1)[1].strip() for n in zipfile.ZipFile(wheel).namelist() if n.endswith(".dist-info/METADATA") for l in zipfile.ZipFile(wheel).read(n).decode().splitlines() if l.startswith("Requires-Dist:")]
check("PyYAML>=5.4" in _req and not any(r.startswith("pyyaml") for r in _req), f"PyYAML is asked for as piwheels spells it (pip 23.0 rejects the lower-case spelling and compiles it): {_req}")
m = mock()
for i,(n,t) in enumerate([("Hilltop Hiker","Morning all, clear skies up here"),("Canal Boat Ted","Anyone hearing me from the lock?")]):
    m.add(n,t,["A7","2F"],ago=1500-i*60)
storage = PluginStorage(os.path.join(TMP, "plugins")); storage.ensure_root()
rt = PluginRuntime(storage)
info = rt.install_wheel(wheel, man)
rel = Path(info["release_dir"])
check((rel/"spamguard-ui"/"index.html").is_file() or any(rel.rglob("spamguard-ui/index.html")), "doorway page installed")
cfg = storage.read_config(man.id)
check(cfg.get("mode")=="monitor" and cfg.get("api_key")=="" and cfg.get("listen_port")==8091, "default settings seeded: "+str(cfg))
port = 18197
cfg.update({"api_key":"t", "openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}", "listen_port":port, "mode":"protect"})
storage.write_config(man.id, cfg)
st = storage.read_state(man.id); st["enabled"]=True; storage.write_state(man.id, st)
check(rt.start(man.id)==PluginState.RUNNING, "openHop starts the plugin")
health=None; lasterr=None
for _ in range(120):
    try:
        health=urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status; break
    except Exception as e: lasterr=repr(e); time.sleep(0.5)
check(health==200, f"SpamGuard's page answers: {health}")
if health!=200: print("      last error:", lasterr, "| proxies:", {k:v for k,v in os.environ.items() if "proxy" in k.lower()}); print("      plugin log:", " | ".join(storage.tail_log(man.id, 15))[-1500:])
for i in range(8): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D","E1"])
time.sleep(9)
names=[r.get("name","") for r in m.policy["policy_engine"]["rules"]]
check(any(n.startswith("spamguard:") for n in names) and "my own rule" in names, "blocks written, operator's own rule kept: "+str(len(names)))
s=json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=5).read())
check(s["update"]["plugin"] is True and not s["update"]["managed_update"] and s["update"]["installer_ready"], "plugin offers its own Update button")
data = storage.paths_for(man.id).data_dir
check((data/"state.json").is_file(), "what it learns is kept in the plugin's data folder")
check(json.loads((data/"runtime.json").read_text()).get("web_page_port")==port, "status note for openHop's dashboard")
t0=time.time(); rt.stop(man.id); took=time.time()-t0
check(took < 5, f"stops promptly when openHop asks ({took:.1f}s)")
check(rt.get_state(man.id)!=PluginState.RUNNING, "stopped")
log="\n".join(storage.tail_log(man.id, 200))
check("Traceback" not in log, "no errors in the plugin log")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
