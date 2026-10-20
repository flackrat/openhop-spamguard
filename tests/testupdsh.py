# The updater script for normal installs writes how far it has got (a percentage that only goes up) and the
# last two lines the installer printed, to the status file the Update box reads. Runs update.sh for real
# against a made-up GitHub (a local web server), a made-up release and fake systemctl/curl. Nothing real is touched.
import sys, os, json, time, threading, subprocess, tarfile, io, tempfile, http.server, shutil
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="sgupd-")
STATE, APP, BIN, SRV = (os.path.join(T, d) for d in ("state", "app", "bin", "srv"))
for d in (STATE, APP, BIN, SRV): os.makedirs(d)
open(os.path.join(APP, "spamguard.py"), "w").write('VERSION = "9.9.8"\n')
open(os.path.join(T, "config.yaml"), "w").write("update_repo: made/up\n")

def release(tag, install_body):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        def add(name, data):
            ti = tarfile.TarInfo(f"spamguard-{tag}/{name}"); ti.size = len(data); ti.mode = 0o755; tf.addfile(ti, io.BytesIO(data))
        add("spamguard.py", f'VERSION = "{tag[1:]}"\n'.encode()); add("install.sh", install_body.encode())
    d = os.path.join(SRV, "made", "up", "releases", "download", tag); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"spamguard-{tag}.tar.gz"), "wb").write(buf.getvalue())
GOOD = "#!/bin/bash\nfor i in $(seq 1 14); do echo \"[$i/14] Setting up part $i\"; sleep 0.6; done\n"
BAD = "#!/bin/bash\nfor i in 1 2 3; do echo \"working on part $i\"; sleep 0.5; done\necho 'ERROR: part 4 could not be installed'\nexit 1\n"
release("v9.9.9", GOOD); release("v9.9.10", BAD)

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=SRV, **k)
    def log_message(s, *a): pass
    def do_GET(s):
        if s.path.endswith(".tar.gz"): time.sleep(0.8)   # a download that takes a moment, so the early percentage can be seen
        super().do_GET()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
# fake systemctl (everything is active) and a curl that says the new version answers on its health page
open(os.path.join(BIN, "systemctl"), "w").write("#!/bin/bash\nexit 0\n")
real = shutil.which("curl")
open(os.path.join(BIN, "curl"), "w").write(f'#!/bin/bash\nfor a in "$@"; do case "$a" in *127.0.0.1:8091/health*) exit 0;; esac; done\nexec {real} "$@"\n')
for f in ("systemctl", "curl"): os.chmod(os.path.join(BIN, f), 0o755)
env = dict(os.environ, PATH=BIN + ":" + os.environ["PATH"], SG_CONF=os.path.join(T, "config.yaml"), SG_APP=APP, SG_STATE=STATE,
           SG_GH_API=base + "/api", SG_GH_WEB=base)

def run(version):
    samples, stop = [], threading.Event()
    def watch():
        while not stop.is_set():
            try: samples.append(json.load(open(os.path.join(STATE, "update-status.json"))))
            except Exception: pass
            time.sleep(0.2)
    th = threading.Thread(target=watch, daemon=True); th.start()
    r = subprocess.run(["bash", os.path.join(REPO, "update.sh"), "--version", version], env=env, capture_output=True, text=True, timeout=240)
    time.sleep(0.5); stop.set(); th.join()
    return r, samples

r, sm = run("v9.9.9")
pcts = [x["pct"] for x in sm if "pct" in x]
check(sm and sm[-1]["state"] == "done" and sm[-1].get("pct") == 100, "a finished update ends on done at 100%: " + str(sm[-1:] ) + r.stderr[-200:])
check(len(pcts) >= 4 and pcts == sorted(pcts), "the percentage only goes up: " + str(pcts))
check(min(pcts) <= 10 and any(30 <= p <= 85 for p in pcts), "it starts low and passes through the installing range: " + str(pcts))
lines = [x.get("lines") for x in sm if x.get("lines")]
check(lines and all(len(l) <= 2 for l in lines) and any("Setting up part" in l[-1] for l in lines), "the last installer lines are in the status: " + str(lines[-1:]))
check("lines" not in sm[-1], "a finished update carries no output lines")
check(not os.path.exists(os.path.join(STATE, "update-status.json.tmp")), "no half-written status file left")
r, sm = run("v9.9.10")
check(sm[-1]["state"] == "failed" and "installer for v9.9.10 failed" in sm[-1]["message"], "a failed install says so: " + str(sm[-1]))
check("part 4 could not be installed" in " ".join(sm[-1].get("lines") or []), "and shows the lines that explain why: " + str(sm[-1].get("lines")))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
