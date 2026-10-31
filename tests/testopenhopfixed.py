# SpamGuard recognises an openHop that already has its own fix for the rule-check bug (cache cleared at the start
# of each check), reports it as safe, and never asks to patch it. An unfixed openHop is still reported unsafe.
# The sources below are short stand-ins in the same shape as openHop's policy engine. Nothing real is used.
import sys, os, tempfile, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

UNFIXED='''class PolicyEngine:
    def __init__(self):
        self._channel_decrypt_cache = {}
    def _decrypt(self, packet):
        packet_key = id(packet)
        cached = self._channel_decrypt_cache.get(packet_key)
        self._channel_decrypt_cache[packet_key] = 1
    def evaluate(self, packet, context):
        if not self.enabled:
            return None
        for rule in self.rules:
            pass
'''
FIXED_UPSTREAM=UNFIXED.replace("        for rule in self.rules:","        # Only keep decrypt results for this call\n        self._channel_decrypt_cache.clear()\n\n        for rule in self.rules:")
PATCHED_BY_US=UNFIXED.replace("        for rule in self.rules:","        # spamguard-fix: clear decrypt cache\n        self._channel_decrypt_cache.clear()\n        for rule in self.rules:")
CLEAR_ELSEWHERE=UNFIXED+"    def other(self):\n        self._channel_decrypt_cache.clear()\n"
REWRITTEN="class PolicyEngine:\n    def evaluate(self, packet, context):\n        for rule in self.rules:\n            pass\n"

def state(src):
    d=tempfile.mkdtemp(); os.makedirs(d+"/repeater")
    open(d+"/repeater/policy_engine.py","w").write(src)
    m=mock(); g=guard(m, openhop_dir=d)
    return g
check(state(UNFIXED).openhop_rulecheck_fix() is False,"an openHop without the fix is reported unsafe")
check(state(FIXED_UPSTREAM).openhop_rulecheck_fix() is True,"openHop's own fix is recognised")
check(state(PATCHED_BY_US).openhop_rulecheck_fix() is True,"our patch is recognised")
check(state(CLEAR_ELSEWHERE).openhop_rulecheck_fix() is False,"a clear somewhere else does not count")
check(state(REWRITTEN).openhop_rulecheck_fix() is True,"a rewritten checker without the old cache is not flagged")

# A fixed openHop is never patched; an unfixed one is (so the check is real, not just skipped)
import spamguard as sg
sg.install_kind=lambda: "normal"
_real=os.path.exists
sg.os.path.exists=lambda p: True if p=="/etc/systemd/system/openhop-spamguard-update.path" else _real(p)
def asks(src):
    g=state(src); asked=[]
    g.request_openhop_fix=lambda why="": asked.append(why)
    g.started=0; g._fix_requested=0
    g._maybe_fix_openhop()
    return bool(asked)
check(asks(UNFIXED) is True,"control: an unfixed openHop is patched")
check(asks(FIXED_UPSTREAM) is False,"a fixed openHop is left alone")
check(asks(REWRITTEN) is False,"a rewritten checker is left alone")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
