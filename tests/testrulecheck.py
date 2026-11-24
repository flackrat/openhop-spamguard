# Reading openHop's rule checker for the known decrypt-cache fault: the real upstream file, the patched one, a future
# fixed shape, an unfamiliar shape (unknown, never "safe"), a missing file, an upgrade that removes the patch, and what
# the page and Health say for each kind of install. No real names or places.
import os, re, glob, tempfile, shutil, time, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
R=sg.rulecheck_state
real=glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),".openhop","**","repeater","policy_engine.py"),recursive=True)
if real:
    src=open(real[0],encoding="utf-8").read()
    check(R(src) is False,"the real openHop file at the pinned commit has the fault")
    patched=src.replace("def evaluate(self","def evaluate(self",1)
    m=re.search(r"(def evaluate\(.*?\n)(\s+)",src,re.S)
    if m:
        patched=src[:m.end(1)]+m.group(2)+"self._channel_decrypt_cache.clear()  # spamguard-fix: clear decrypt cache\n"+src[m.end(1):]
        check(R(patched) is True,"the patched real file is safe")
else:
    print("note: openHop not checked out here (run_all.sh fetches it); using shapes only")
bad='''class PolicyEngine:
    def evaluate(self, packet):
        for rule in self.rules: pass
    def _sender(self, packet):
        packet_key = id(packet)
        if packet_key in self._channel_decrypt_cache: return self._channel_decrypt_cache[packet_key]
'''
check(R(bad) is False,"the fault in its known shape")
fixed_clear=bad.replace("def evaluate(self, packet):\n","def evaluate(self, packet):\n        self._channel_decrypt_cache.clear()\n")
check(R(fixed_clear) is True,"cleared at the start of each check: safe")
future=bad.replace("packet_key = id(packet)","packet_key = bytes(packet.payload)")
check(R(future) is True,"keyed on the packet's content: safe")
renamed=bad.replace("_channel_decrypt_cache","_dc")
check(R(renamed) is None,"keyed on identity under another name: unknown, not safe")
check(R("print('hello')") is None,"an unrelated file: unknown")
check(R("class PolicyEngine:\n    def evaluate(self, p):\n        return None\n") is True,"no cache at all: safe")

d=tempfile.mkdtemp(); pe=os.path.join(d,"x","repeater"); os.makedirs(pe)
m=mock(); g=guard(m, floodguard=False, openhop_dir=d)
check(g.openhop_rulecheck_fix() is None,"no file found: unknown")
open(os.path.join(pe,"policy_engine.py"),"w").write(bad); g._rfix_cache=None
check(g.openhop_rulecheck_fix() is False,"the fault found on disk")
open(os.path.join(pe,"policy_engine.py"),"w").write(fixed_clear); g._rfix_cache=None
check(g.openhop_rulecheck_fix() is True,"after the fix")
open(os.path.join(pe,"policy_engine.py"),"w").write(bad); g._rfix_cache=(time.time()-301,True)
check(g.openhop_rulecheck_fix() is False,"an openHop upgrade that removes the fix is noticed within five minutes")
# what Health says, per install kind
SAVE=(sg.IN_PLUGIN,sg.openhop_in_container)
sg.IN_PLUGIN=True; sg.openhop_in_container=lambda: True; g._rfix_cache=None
w=" ".join(g.health()["warnings"])
check("container" in w and "less reliable" in w,"inside openHop's container: says blocks are less reliable until openHop fixes it")
check(g.status()["metrics"]["rulecheck_where"]=="container","the page is told")
shutil.rmtree(pe); g._rfix_cache=None
sg.openhop_in_container=lambda: False
import importlib.util as _iu; _fs=_iu.find_spec; _iu.find_spec=lambda n,*a: None if n=="repeater.policy_engine" else _fs(n,*a)
w=" ".join(g.health()["warnings"])
check("couldn't check openHop" in w,"a plugin that can't find openHop's file says so rather than nothing")
_iu.find_spec=_fs
sg.IN_PLUGIN,sg.openhop_in_container=SAVE
shutil.rmtree(d)
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
