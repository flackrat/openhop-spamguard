# Moving to the plugin: the one-time handover link is only followed to the previous SpamGuard on this machine or a
# home network, at /handover, and its data is size-capped. Made-up addresses.
import os, sys, json, tempfile, io
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"plugin"))
import plugin as P
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
for u in ("http://127.0.0.1:8091/handover?key=x","http://192.168.1.20:8091/handover?key=x","http://172.17.0.1:8091/handover",
          "http://localhost:8091/handover","http://[::1]:8091/handover"):
    check(P.handover_url_ok(u),"followed: "+u)
for u in ("http://8.8.8.8/handover","https://q-site.example/handover","http://127.0.0.1:8091/status","file:///etc/passwd",
          "http://user:pw@127.0.0.1/handover","http://100.64.1.1/handover","ftp://127.0.0.1/handover","",None,"handover"):
    check(not P.handover_url_ok(u),"ignored: %r"%(u,))
d=tempfile.mkdtemp(); cfgp=os.path.join(d,"config.json")
def run(url, body):
    json.dump({"import_from":url,"api_key":"t"},open(cfgp,"w"))
    for n in ("state.json",):
        if os.path.exists(os.path.join(d,n)): os.remove(os.path.join(d,n))
    import urllib.request, time
    class R(io.BytesIO):
        def __enter__(s): return s
        def __exit__(s,*a): pass
    calls=[]
    orig_open, orig_sleep = urllib.request.urlopen, time.sleep
    urllib.request.urlopen=lambda u,timeout=0: (calls.append(u), R(body))[1]
    time.sleep=lambda s: None
    try: P.take_over(d,cfgp)
    finally: urllib.request.urlopen, time.sleep = orig_open, orig_sleep
    return calls, os.path.exists(os.path.join(d,"state.json")), json.load(open(cfgp))
calls,got,cfg=run("http://127.0.0.1:8091/handover?key=x", json.dumps({"blocks":{}}).encode())
check(got and len(calls)==1 and "import_from" not in cfg,"a good link is followed once, then forgotten")
calls,got,cfg=run("https://q-site.example/handover", json.dumps({"blocks":{}}).encode())
check(not calls and not got and "import_from" not in cfg,"a bad link is never fetched, and is forgotten")
P.HANDOVER_MAX=1000
calls,got,cfg=run("http://127.0.0.1:8091/handover", json.dumps({"blocks":{},"pad":"x"*5000}).encode())
check(not got,"oversized data is refused")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
