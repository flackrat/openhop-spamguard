# 6.28.0: the updater checks a download against the checksum published with the release before installing it.
# Runs update.sh for real against a made-up GitHub (a local web server) with fake systemctl/curl. Nothing real is touched.
import sys, os, json, threading, subprocess, tarfile, io, tempfile, http.server, shutil, hashlib
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="sgver-")
STATE, APP, BIN, SRV = (os.path.join(T, d) for d in ("state", "app", "bin", "srv"))
for d in (STATE, APP, BIN, SRV): os.makedirs(d)
open(os.path.join(T, "config.yaml"), "w").write("update_repo: made/up\n")

def release(tag, sums="good"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        def add(name, data):
            ti = tarfile.TarInfo(f"spamguard-{tag}/{name}"); ti.size = len(data); ti.mode = 0o755; tf.addfile(ti, io.BytesIO(data))
        add("spamguard.py", f'VERSION = "{tag[1:]}"\n'.encode()); add("install.sh", b"#!/bin/bash\necho installed > \"$SG_MARK\"\n")
    d = os.path.join(SRV, "made", "up", "releases", "download", tag); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"spamguard-{tag}.tar.gz"), "wb").write(buf.getvalue())
    h = hashlib.sha256(buf.getvalue()).hexdigest()
    if sums == "good": open(os.path.join(d, "SHA256SUMS"), "w").write(f"{h}  spamguard-{tag}.tar.gz\n")
    elif sums == "wrong": open(os.path.join(d, "SHA256SUMS"), "w").write(f"{'0'*64}  spamguard-{tag}.tar.gz\n")
    elif sums == "other": open(os.path.join(d, "SHA256SUMS"), "w").write(f"{h}  something-else.tar.gz\n")
    # "none": no checksum file published
release("v7.0.1", "good"); release("v7.0.2", "wrong"); release("v7.0.3", "none"); release("v7.0.4", "other")
release("v6.27.9", "none")   # an older release, published before checksums existed

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=SRV, **k)
    def log_message(s, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
open(os.path.join(BIN, "systemctl"), "w").write("#!/bin/bash\nexit 0\n")
real = shutil.which("curl")
open(os.path.join(BIN, "curl"), "w").write(f'#!/bin/bash\nfor a in "$@"; do case "$a" in *127.0.0.1:8091/health*) exit 0;; esac; done\nexec {real} "$@"\n')
for f in ("systemctl", "curl"): os.chmod(os.path.join(BIN, f), 0o700)
MARK = os.path.join(T, "mark")
env = dict(os.environ, PATH=BIN + ":" + os.environ["PATH"], SG_CONF=os.path.join(T, "config.yaml"), SG_APP=APP, SG_STATE=STATE,
           SG_GH_API=base + "/api", SG_GH_WEB=base, SG_MARK=MARK)

def run(version):
    open(os.path.join(APP, "spamguard.py"), "w").write('VERSION = "6.0.0"\n')
    if os.path.exists(MARK): os.remove(MARK)
    r = subprocess.run(["bash", os.path.join(REPO, "update.sh"), "--version", version], env=env, capture_output=True, text=True, timeout=120)
    st = json.load(open(os.path.join(STATE, "update-status.json")))
    return st, os.path.exists(MARK)

st, ran = run("v7.0.1")
check(st["state"] == "done" and ran, "a download that matches its published checksum is installed: " + str(st))
st, ran = run("v7.0.2")
check(st["state"] == "failed" and not ran and "checksum" in st["message"], "a download that does not match is refused and nothing runs: " + str(st))
st, ran = run("v7.0.3")
check(st["state"] == "failed" and not ran and "without checksums" in st["message"], "a new release with no checksums is refused: " + str(st))
st, ran = run("v7.0.4")
check(st["state"] == "failed" and not ran, "a checksum file that does not list the download is refused: " + str(st))
st, ran = run("v6.27.9")
check(st["state"] == "done" and ran, "an older release without checksums can still be installed (to go back): " + str(st))
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
