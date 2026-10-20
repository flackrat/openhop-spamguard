# Updating the openHop plugin: SpamGuard checks, before openHop removes the running version, that the new
# version's libraries can be installed from ready-made builds. A clear "no build exists" stops the update
# with nothing changed (and an Update anyway button); no network, no pip or any other doubt lets it go ahead.
# Nothing here touches the network: pip and the download are replaced. All data is made up.
import sys, io, zipfile, time, subprocess, urllib.request
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def wheel(requires=("pycryptodome>=3.15","PyYAML>=5.4")):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("openhop_spamguard-9.9.9.dist-info/METADATA","Metadata-Version: 2.1\nName: openhop-spamguard\nVersion: 9.9.9\n"+
                   "".join(f"Requires-Dist: {r}\n" for r in requires)+"Requires-Dist: pytest; extra == 'dev'\n")
        z.writestr("openhop_spamguard/__init__.py","")
    return b.getvalue()
class R:
    def __init__(s,rc=0,out="",err=""): s.returncode=rc; s.stdout=out; s.stderr=err
calls=[]
def fake(result):
    def run(cmd,**kw):
        calls.append(cmd)
        if isinstance(result,Exception): raise result
        return result
    return run
real_run=subprocess.run
def with_pip(result):
    subprocess.run=fake(result)
g=guard(mock())

try:
    calls.clear(); with_pip(R(0))
    check(g.plugin_preflight(wheel()) is None,"ready-made builds exist: no objection")
    c=calls[0]
    check("--only-binary=:all:" in c and "pycryptodome>=3.15" in c and "PyYAML>=5.4" in c,"it asks pip for the wheel's own requirements, binary only: "+" ".join(c[3:9]))
    check(not any("pytest" in x for x in c),"and not for optional extras")
    check("--no-deps" in c and "--disable-pip-version-check" in c,"without dependencies or the version check")

    with_pip(R(1,"","ERROR: Could not find a version that satisfies the requirement PyYAML>=5.4 (from versions: none)\nERROR: No matching distribution found for PyYAML>=5.4"))
    why=g.plugin_preflight(wheel())
    check(why and "stopped before anything was changed" in why and "PyYAML" in why and "pycryptodome" in why,"a clear 'no build exists' stops it, naming the libraries: "+str(why)[:90])
    check(why and "Plugins page" in why and "Update anyway" in why,"and says what to do instead")

    with_pip(R(1,"","WARNING: Retrying (Retry(total=0)) after connection broken by 'NewConnectionError'\nERROR: Could not find a version that satisfies the requirement PyYAML (from versions: none)\nERROR: No matching distribution found for PyYAML"))
    check(g.plugin_preflight(wheel()) is None,"no network (pip gives the same final error): the update goes ahead")
    with_pip(R(1,"","ERROR: Could not fetch URL https://pypi.org/simple/pyyaml/: There was a problem confirming the ssl certificate"))
    check(g.plugin_preflight(wheel()) is None,"a certificate or proxy problem: goes ahead")
    with_pip(R(1,"","/usr/bin/python: No module named pip"))
    check(g.plugin_preflight(wheel()) is None,"pip not available: goes ahead")
    with_pip(R(2,"","ERROR: some other failure"))
    check(g.plugin_preflight(wheel()) is None,"any other failure: goes ahead")
    with_pip(subprocess.TimeoutExpired("pip",120))
    check(g.plugin_preflight(wheel()) is None,"pip taking too long: goes ahead")
    with_pip(OSError("no such file"))
    check(g.plugin_preflight(wheel()) is None,"cannot run pip at all: goes ahead")
    calls.clear(); with_pip(R(1,"","No matching distribution found"))
    check(g.plugin_preflight(wheel(()))is None and not calls,"a wheel with no requirements isn't checked")
    check(g.plugin_preflight(b"not a zip") is None,"a damaged file isn't this check's problem")

    # ---- the update itself
    sg.IN_PLUGIN=True; sg.managed_update=lambda: None
    uploaded=[]; restarted=[]
    g._upload_wheel=lambda name,data: uploaded.append(name) or {}
    g._plugin_api=lambda *a,**k: restarted.append(a) or {}
    g._save_state=lambda *a,**k: None
    g._follow_install_progress=lambda stop: None
    W=wheel()
    class Resp:
        headers={"Content-Length":str(len(W))}
        def __init__(s): s.b=io.BytesIO(W)
        def read(s,n=-1): return s.b.read(n)
        def __enter__(s): return s
        def __exit__(s,*a): pass
    real_open=urllib.request.urlopen; urllib.request.urlopen=lambda *a,**k: Resp()
    def wait():
        for _ in range(100):
            if g.plugin_update.get("state")!="running": return
            time.sleep(0.05)
    NO=R(1,"","ERROR: No matching distribution found for PyYAML>=5.4")
    with_pip(NO); uploaded.clear(); restarted.clear()
    g.update_action("install_update",{"version":"9.9.9"}); wait()
    pu=g.plugin_update
    check(pu["state"]=="failed" and pu.get("can_force") and "stopped before anything was changed" in pu["message"],"the update stops and offers Update anyway: "+str(pu)[:100])
    check(not uploaded and not restarted,"nothing was handed to openHop, so nothing was removed")
    check(pu["pct"]<=35,"and no progress is claimed: %s"%pu["pct"])

    uploaded.clear(); restarted.clear()
    g.update_action("install_update",{"version":"9.9.9","force":True}); wait()
    check(uploaded and restarted and g.plugin_update.get("state")!="failed","Update anyway goes ahead: "+str(g.plugin_update)[:80])

    g.plugin_update={}   # a finished update leaves "running": the process restarts
    uploaded.clear(); restarted.clear(); calls.clear(); g.cfg["plugin_preflight"]=False
    g.update_action("install_update",{"version":"9.9.9"}); wait()
    check(uploaded and not calls,"with the check turned off in the config it isn't run")
    g.cfg["plugin_preflight"]=True
    g.plugin_update={}; uploaded.clear(); with_pip(R(0))
    g.update_action("install_update",{"version":"9.9.9"}); wait()
    check(uploaded,"with builds available the update goes ahead as before")
finally:
    subprocess.run=real_run
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
