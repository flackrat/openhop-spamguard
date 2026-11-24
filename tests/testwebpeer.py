# The page and its data answer devices on this machine or a private network. Without a page password, a device on
# the open internet gets nothing, whatever name it says it is visiting; with the password it gets in as before.
# Addresses below are made up or well-known examples; nothing is real.
import json, threading, http.client, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

P=sg.peer_is_local
for a in ("127.0.0.1","::1","192.168.1.20","10.4.0.9","172.17.0.1","fd12:3456::1","fe80::2%eth0","169.254.10.1","::ffff:192.168.1.20"):
    check(P(a),"local or private: "+a)
for a in ("1.2.3.4","5.6.7.8","8.8.8.8","2001:4860::8888","::ffff:8.8.4.4","100.63.255.1","0.0.0.0","","not an address",None):
    check(not P(a),"on the open internet, or nonsense: %r"%(a,))
# shared and reserved ranges are not trusted unless listed (internet providers share 100.64.0.0/10 between customers)
for a in ("100.100.7.3","100.64.0.1","192.0.0.8","198.18.0.5","240.0.0.1","203.0.113.7","2001:db8::1"):
    check(not P(a),"not trusted by default: "+a)
nets=sg.parse_networks(["100.64.0.0/10","nonsense","fd7a:115c:a1e0::/48"])
check(len(nets)==2,"bad entries in the list are ignored")
check(P("100.100.7.3",nets) and P("fd7a:115c:a1e0::5",nets) and not P("100.128.0.1",nets),"a listed network is trusted, and only that one")

m=mock(); g=guard(m, floodguard=False)
FAKE=["1.2.3.4"]
H=sg.make_handler(g)
class AsIf(H):
    def setup(self):
        super().setup(); self.client_address=(FAKE[0],40000)
srv=sg.QuietServer(("127.0.0.1",0),AsIf); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
def req(method,path,body=None,headers=None):
    c=http.client.HTTPConnection("127.0.0.1",port,timeout=10)
    c.request(method,path,body=body,headers=headers or {})
    r=c.getresponse(); d=r.read(); c.close(); return r.status,d
J={"Content-Type":"application/json"}
before=g.cfg["level"]
# from the internet, no password: nothing, even with a home-looking Host
for path in ("/","/status","/rules","/health","/evidence?days=1"):
    st,d=req("GET",path,headers={"Host":"192.168.1.20:8091"})
    check(st==403 and b"page password" in d,"no answer to the internet for %s: %s %s"%(path,st,d[:80]))
st,_=req("POST","/settings",json.dumps({"level":90}),{**J,"Host":"192.168.1.20"})
check(st==403 and g.cfg["level"]==before,"and no changes from it")
st,_=req("POST","/install_update",json.dumps({"version":"99.0.0"}),{**J,"Host":"localhost"})
check(st==403,"nor updates")
# from the home network, no password: as before
FAKE[0]="192.168.1.50"
st,_=req("GET","/status",headers={"Host":"192.168.1.20:8091"}); check(st==200,"the home network still gets the page")
st,_=req("POST","/settings",json.dumps({}),{**J,"Host":"192.168.1.20"}); check(st==200,"and can still make changes")
st,_=req("GET","/status",headers={"Host":"spamguard.attacker.example"}); check(st==403,"the Host check against other sites still works")
FAKE[0]="100.101.2.3"
st,d=req("GET","/status",headers={"Host":"pi"}); check(st==403 and b"trusted_networks" in d,"a Tailscale address is refused until listed, and told how")
try:
    g.apply_settings({"trusted_networks":"100.64.0.0/10"})
except ValueError as ex: check(False,str(ex))
st,_=req("GET","/status",headers={"Host":"pi"}); check(st==200,"once listed, it gets the page")
for bad in ("0.0.0.0/0","1.0.0.0/4","not a net"):
    try: g.apply_settings({"trusted_networks":bad}); check(False,"refused: "+bad)
    except ValueError: check(True,"")
g.apply_settings({"trusted_networks":[]})
# with a password, the internet gets in with it, and only with it
g.settings["listen_api_key"]="q-made-up-key"; g.rebuild_cfg()
FAKE[0]="1.2.3.4"
st,_=req("GET","/status"); check(st==401,"password set: without it, refused")
st,_=req("GET","/status",headers={"X-API-Key":"q-made-up-key"}); check(st==200,"with it, the page answers from anywhere")
st,_=req("POST","/settings",json.dumps({}),{**J,"X-API-Key":"q-made-up-key"}); check(st==200,"and changes work")
srv.shutdown()
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
