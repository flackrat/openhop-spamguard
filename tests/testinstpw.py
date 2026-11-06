# 6.28.0: a fresh install can set a random web page password; updates and existing passwords are left alone.
# Runs only the password block of install.sh against a temporary config file.
import sys, os, re, subprocess, tempfile
ok = fail = 0
def check(c, msg):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print("FAIL", msg)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(REPO, "install.sh")).read()
blk = src[src.index("# --- web page password"):src.index("# openHop rule-check fix")]
T = tempfile.mkdtemp(prefix="sgpw-")
def run(conf_text, sgpw=None):
    conf = os.path.join(T, "config.yaml"); open(conf, "w").write(conf_text)
    env = dict(os.environ, SG_CONF_FILE=conf)
    env.pop("SG_PASSWORD", None)
    if sgpw is not None: env["SG_PASSWORD"] = sgpw
    # a python on PATH stands in for openHop's venv one
    script = blk.replace("/opt/openhop_repeater/venv/bin/python", sys.executable)
    r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return open(conf).read(), r.stdout
base = 'listen_port: 8091\nlisten_api_key: ""\nmode: monitor\n'
c, out = run(base, "1")
m = re.search(r'^listen_api_key: "([A-Za-z0-9_-]{20,})"$', c, re.M)
check(m and m.group(1) in out, "SG_PASSWORD=1 sets a long random password and shows it once: " + c)
check("mode: monitor" in c and "listen_port: 8091" in c, "other settings are untouched")
c2, _ = run(base, "1"); p2 = re.search(r'"([^"]+)"', c2.split("listen_api_key:")[1]).group(1)
check(p2 != m.group(1), "each install gets a different password")
c, out = run(base, "0")
check('listen_api_key: ""' in c and "Tip" not in out, "SG_PASSWORD=0 leaves it empty without nagging")
c, out = run(base)
check('listen_api_key: ""' in c and "Tip" in out, "a scripted install (no terminal) leaves it empty and says how to set one")
c, out = run('listen_api_key: "mine"\n', "1")
check('listen_api_key: "mine"' in c and not out, "an existing password is never replaced")
c, out = run("listen_api_key: ''  # none yet\n", "1")
check("none yet" not in c or 'listen_api_key: "' in c, "single-quoted empty value is also recognised")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
