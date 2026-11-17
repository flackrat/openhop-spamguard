# The scrambled evidence download hides every name and node key, keeps them consistent, and keeps the rest usable.
# All names, keys and messages are made up.
import sys, os, json, tempfile, logging
from harness import *
logging.disable(logging.CRITICAL)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
d=tempfile.mkdtemp(prefix="sgtest-scr-")
e=sg.EvidenceLog(d)
NAMES=["Pat Example","Hilltop Node","Sam Sample"]
KEY="aa11"*16   # an obviously made-up node key
e.add({"type":"msg","sender":"Pat Example","text":"morning Sam Sample, signal good","channel":"Public","path":["A1"]})
e.add({"type":"advert","name":"Hilltop Node","key":KEY,"path":["A1"],"hops":1})
e.add({"type":"advert","name":"Pat Example","key":KEY[::-1],"path":["B2"],"hops":1})
e.add({"type":"sense","who":"Sam Sample","value":"buy now","count":3,"held":True})
e.add({"type":"block","event":"add","key":"persist:Pat Example","kind":"name","value":"Pat Example","reason":"Pat Example repeating","source":"slowrepeat","exempt_sender":None})
e.add({"type":"label","label":"spam","sender":"Sam Sample","text":"hello from Hilltop Node","path":["A1"],"packet":"p1"})
plain=e.export(7,False); out=e.export(7,True)
check(all(n in plain for n in NAMES),"the unscrambled download still has everything")
for n in NAMES: check(n not in out,"name hidden everywhere: "+n)
check(KEY not in out and KEY[::-1] not in out,"node keys hidden")
recs=[json.loads(l) for l in out.splitlines()]
adv=[r for r in recs if r["type"]=="advert"]
check(all(r["name"].startswith("N-") and r["key"].startswith("K-") for r in adv),"adverts carry codes")
check(adv[0]["key"]!=adv[1]["key"],"different nodes keep different key codes")
msg=recs[0]
check(adv[1]["name"]==msg["sender"],"a node's advert name and its messages share one code")
sense=[r for r in recs if r["type"]=="sense"][0]
lab=[r for r in recs if r["type"]=="label"][0]
check(sense["who"]==lab["sender"],"the same person gets the same code in every record")
blk=[r for r in recs if r["type"]=="block"][0]
check(msg["sender"] in blk["key"] and msg["sender"] in blk["reason"],"hold keys and reasons use the codes too")
check(sense["value"]=="buy now" and adv[0]["hops"]==1 and msg["channel"]=="Public","the rest is left as it was")
out2=e.export(7,True)
check(json.loads(out2.splitlines()[0])["sender"]!=msg["sender"],"each download uses fresh codes, so two can't be joined up")
import shutil; shutil.rmtree(d,ignore_errors=True)
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
