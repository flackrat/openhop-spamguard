# Keeps the wording brief: no explanation on the page, in a setting or in Activity may grow past these lengths.
# If one does, say it in fewer words, or move the detail to docs/.
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import spamguard as sg
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
PAGE, SETTING, NOTE = 240, 480, 180
root=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ui=open(os.path.join(root,"ui.html"),encoding="utf-8").read()
for m in re.finditer(r'<p class="(?:lead|explain|more|note|help)"[^>]*>(.*?)</p>', ui, re.S):
    t=re.sub(r'\$\{[^}]*\}','…',re.sub(r'<[^>]+>','',m.group(1)))
    check(len(t)<=PAGE, f"page text over {PAGE} characters ({len(t)}): {t[:70]}")
for meta in sg.SETTINGS_META:
    n=len(meta.get("help",""))+len(meta.get("risk",""))
    check(n<=SETTING, f"setting {meta['key']} has {n} characters of description (limit {SETTING})")
src=open(os.path.join(root,"spamguard.py"),encoding="utf-8").read()
for m in re.finditer(r'self\.note\(((?:f?"(?:[^"\\]|\\.)*"\s*)+)', src):
    t=re.sub(r'\{[^}]*\}','…',"".join(re.findall(r'"((?:[^"\\]|\\.)*)"',m.group(1))))
    check(len(t)<=NOTE, f"Activity message over {NOTE} characters ({len(t)}): {t[:70]}")
readme=open(os.path.join(root,"README.md"),encoding="utf-8").read()
check(len(readme.split())<=3000, f"README is {len(readme.split())} words; keep the front page under 3000 and put detail in docs/")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
