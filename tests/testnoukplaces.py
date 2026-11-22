# Test data never uses real places near the owner's mesh: every location in the repository's tests, docs and code is
# a made-up spot in the USA. Fails on any coordinate pair inside Britain and Ireland, written as "lat, lon",
# "lat lon", or "lat": .. "lon": .. (also lat= .. lon=). Added in 6.45.0 after test coordinates near a real
# repeater reached a branch.
import os, re, subprocess, sys
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files=subprocess.check_output(["git","ls-files"],cwd=REPO).decode().split()
files=[f for f in files if f.endswith((".py",".html",".md",".json",".yaml",".yml",".txt",".sh",".js")) and not f.startswith(("tests/.axe","tests/.leaflet"))]
NUM=r"-?\d{1,3}\.\d+"
PAIR=re.compile(rf"(?<![\w.])({NUM})(?:\s*,\s*|\s+)({NUM})(?![\w.])")
KEYED=re.compile(rf"""["']?lat["']?\s*[:=]\s*({NUM})[^\n]{{0,80}}?["']?lon["']?\s*[:=]\s*({NUM})""")
def uk(lat,lon): return 49.5<=lat<=61.0 and -11.0<=lon<=2.5
def found(line): return [m for m in list(PAIR.finditer(line))+list(KEYED.finditer(line)) if uk(float(m.group(1)),float(m.group(2)))]
# the check itself works (these are not real places, only shapes)
# (built at run time, so no British coordinate is ever written in the repository, even as a test of this check)
la, lo = 40 + 12, -1 + 0
assert found(f"me=({la}.11,{lo}.22)") and found(f"<{la}.22222 {lo}.33333>") and found(f'{{"lat":{la}.4,"lon":{lo - 1}.2}}') \
    and found(f"lat={la - 1}.5, lon={lo - 2}.1")
assert not found("me=(39.2,-96.5)") and not found('"lat":40.1,"lon":-95.2') and not found("version 6.45.0, 1.5")
bad=[]
for f in files:
    try: text=open(os.path.join(REPO,f),encoding="utf-8").read()
    except (UnicodeDecodeError,FileNotFoundError): continue
    for n,line in enumerate(text.splitlines(),1):
        for m in list(PAIR.finditer(line))+list(KEYED.finditer(line)):
            la,lo=float(m.group(1)),float(m.group(2))
            if uk(la,lo) and "." in m.group(1) and len(m.group(1).split(".")[1])>=1:
                bad.append(f"{f}:{n}")
bad=sorted(set(bad))
for b in bad[:30]: print("FAIL a place in Britain or Ireland:",b)
print(f"{0 if bad else 1} passed, {1 if bad else 0} failed"); sys.exit(1 if bad else 0)
