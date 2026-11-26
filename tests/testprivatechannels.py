# Private channels (read with their own key, not a hashtag's) are treated as personal data: their names are hidden
# like people's names in the scrambled evidence download and never appear in the diagnostic export, and their keys
# never leave the Pi. The repository's own checks stop a channel key being committed. Made-up names and keys only.
import sys, os, json, base64, tempfile, logging, subprocess
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PRIV="Quarry Crew Ops"; KEY=os.urandom(16).hex()   # a fresh made-up key each run, so it is never in the repo
m=mock(); g=guard(m, evidence_log=True, evidence_dir=tempfile.mkdtemp(prefix="sgtest-pc-"))
g.cfg["channels"][PRIV]=KEY; g.cfg["channels"]["#quarryopen"]=sg.hashtag_secret("#quarryopen")
check(g.private_channels()==[PRIV],"a channel with its own key is private; Public and hashtag channels aren't: %s"%g.private_channels())
g.poll_once()
m.add("Quarry Dee","meet at the usual place, "+PRIV+" folks",["A1","B2"],ago=400,key=KEY)
m.add("Quarry Dee","open chat here",["A1","B2"],ago=300,key=sg.hashtag_secret("#quarryopen"))
g.poll_once()
check(any(e.channel==PRIV for e in g.events),"the private channel is read on the Pi")
g.evidence.flush(force=True)
plain=g.evidence.export(7,False); out=g.evidence.export(7,True,private=tuple(g.private_channels()))
check(PRIV in plain,"the unscrambled download, for you only, still has it")
check(PRIV not in out,"the scrambled download hides the private channel's name everywhere, even in message text")
check("C-" in out and "#quarryopen" in out,"it becomes a code, and hashtag channels stay readable")
recs=[json.loads(l) for l in out.splitlines()]; chans={r.get("channel") for r in recs if r.get("type")=="msg"}
check(len([c for c in chans if c and c.startswith("C-")])==1,"one private channel, one code, the same throughout: %s"%chans)
check(KEY not in plain and KEY not in out,"the key is in neither download")
d=json.dumps(g.diagnostics()); check(PRIV not in d and KEY not in d and g.diagnostics()["counts"]["channels_private"]==1,"the diagnostic export has a count only")
g._save_state(force=True); check(KEY not in json.dumps(g.status()),"the page's status doesn't carry the key")
# --- the repository's checks
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","tools")); import privacy_check as pc
al=pc.load_allowed(); kb=base64.b64encode(os.urandom(16)).decode()
check(pc.check_line(f'"{PRIV}": "{KEY}"',al,[])==["channel key"],"the privacy check stops a channel key in hex")
check(pc.check_line(f"psk = {kb}",al,[])==["channel key"],"and in base64")
check(pc.check_line('"Public": "8b3387e9c5cdea6ac9e5edbaa115cd72"',al,[])==[],"the published Public key is fine")
check(pc.check_line("sha256 "+"ab"*32,al,[])==[],"a longer hash isn't mistaken for a key")
gl="/tmp/gl28/gitleaks"
if os.path.exists(gl):
    d2=tempfile.mkdtemp(prefix="sgtest-gl-"); open(os.path.join(d2,"x.json"),"w").write(f'{{"{PRIV}": "{KEY}"}}\n')
    r=subprocess.run([gl,"detect","--no-git","--no-banner","--source",d2,"--config",os.path.join(os.path.dirname(os.path.abspath(__file__)),"..",".gitleaks.toml")],capture_output=True,text=True)
    check(r.returncode!=0,"the leak scanner stops it too")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
