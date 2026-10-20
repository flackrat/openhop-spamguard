# Name scoring: radio callsigns and default device names are people, made-up names still count.
# All names here are made up (Q-prefixes are not issued as callsigns) or generated.
import sys, re, random, string
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
P=[re.compile(r"(?=.*\d)(?=.*[a-z])[a-z0-9]{8}",re.I)]
for n in ["QZ1ABC","QY2XYZ","QX9QRM","qw3abc","QA0BCD1","QB12CDE","QZ1ABC 📡","Dave1985"]:
    check(sg.name_score(n,P)<3,f"{n} reads as a person: {sg.name_score(n,P)}")
for n in ["3FA9C2E1","b07e4d9a"]:
    s=sg.name_score(n,P); check(s==2,f"default device name {n} counts a little: {s}")
for n in ["UD6DWREK","X7KQ2ZPW","QZL33NZ4","RWHRF8Y9","M7QJ42XV","QZ1ABC77"]:
    check(sg.name_score(n,P)>=3,f"made-up name {n} still counts: {sg.name_score(n,P)}")
# Capital-letter abbreviations (made up here) were being counted as spam let through
for n in ["HLDWNTR","PRKSTVN","KLMWRTH","PRKSTVN🐺","🛰HLDWNTR"]:
    s=sg.name_score(n,P); check(s<3,f"capital-letter abbreviation {n} is not a made-up name: {s}")
check(sg.name_score("HLDWNTR",[re.compile("HLDWNTR")])>=2,"a name you list as a pattern still counts")
random.seed(5); A=string.ascii_uppercase+string.digits
R=["".join(random.choice(A) for _ in range(8)) for _ in range(5000)]
rate=sum(sg.name_score(n,P)>=3 for n in R)/len(R)
check(rate>=0.9,f"random 8-character names counted: {rate:.0%}")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
