# 6.42.1: the Overview and the other pages keep working in an hour when the radio only heard packets sent
# straight to it, and a failed page request now says where it failed. Checked through the web handler.
# All data is made up.
import sys, logging, urllib.request, urllib.error
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

RADIO={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":16}
def pkt(ts, route, hops=0):
    return {"id":os.urandom(6).hex(),"timestamp":ts,"type":2,"route":route,"length":60,"rssi":-100,"snr":2.0,
            "transmitted":False,"is_duplicate":False,"packet_hash":os.urandom(8).hex(),
            "original_path":json.dumps([os.urandom(1).hex().upper() for _ in range(hops)]),"payload":""}

class Grab(logging.Handler):
    def __init__(s): super().__init__(); s.msgs=[]
    def emit(s, r): s.msgs.append(r.getMessage())
grab=Grab(); sg.log.addHandler(grab); sg.log.setLevel(logging.WARNING); sg.log.propagate=False

m=mock(); g=guard(m, mode="monitor"); g.radio=dict(RADIO)
g.refresh_openhop_info=lambda *a,**k: None
now=time.time()
# an hour of airtime from direct packets only: nothing flooded, so no flood airtime is recorded for it
g.ingest([pkt(now-60-i, 2) for i in range(5)])
h=g.hist[str(int((now-60)//3600*3600))]   # the packets' own hour (they are a minute old)
check(h.get("ar",0)>0 and "af" not in h, "setup: the hour has airtime and no flood airtime")
try:
    st=g.status(); built=True
except Exception as e:
    built=False; print("error:",type(e).__name__,e)
check(built, "the page data is built")
if built:
    last=st["metrics"]["hourly"][-1]
    check(last["af"]==0, "that hour reads as no flood airtime")
# a mix of hours, including one with flood airtime, still gives a share
g.ingest([pkt(now-4000-i, 1, 3) for i in range(5)] + [pkt(now-4100-i, 2) for i in range(5)])
st=g.status()
shares=[r["af"] for r in st["metrics"]["hourly"] if r["af"] is not None]
check(shares and all(0<=x<=100 for x in shares), "shares across hours stay between 0 and 100")

srv=sg.QuietServer(("127.0.0.1",0),sg.make_handler(g)); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
r=urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=10)
check(r.status==200 and json.loads(r.read()).get("version")==sg.VERSION, "the page request is answered")

# a request that does fail still answers with an error and says where
real=g.status_now
def boom(*a,**k): return {}["x"]
g.status_now=boom
try:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=10); code=200
except urllib.error.HTTPError as e:
    code=e.code
g.status_now=real
check(code==500, "a failing request answers 500")
check(any("KeyError in boom, line" in x for x in grab.msgs), "and the log names where it failed")

# one failing part of the page data leaves the rest of the page working
real_metrics=g.metrics
g.metrics=lambda: {}["x"]
try:
    st2=g.status(); built2=True
except Exception:
    built2=False
check(built2 and st2.get("metrics") is None and st2.get("version")==sg.VERSION and "blocks" in st2,
      "a failing history part comes back empty and the rest is still built")
check(sum("could not be built (KeyError" in x for x in grab.msgs)==1, "and is logged once, with where")
g.status(); check(sum("could not be built (KeyError" in x for x in grab.msgs)==1, "not again for five minutes")
r=urllib.request.urlopen(f"http://127.0.0.1:{port}/status",timeout=10)
check(r.status==200, "the web request is still answered")
g.metrics=real_metrics

# saved hour records from older versions lack newer keys: the history part is built whatever is missing
FULL={"m":9,"c":3,"x":2,"g":1,"a":1.5,"h":{"4C":2},"ar":4000,"af":1200,"pk":9,"gp":4,"dp":1,"dr":300,"ds":1,"fc":1,
      "fx":1,"fs":2.0,"bz":12.0,"nf":-110.0,"nfx":-95.0,"ie":1,"wh":1,"ws":1,"fcl":1,"fcu":1,"fca":1,"fh":{"4C":3},
      "ch":{"Public":{"c":1,"x":1,"m":4}}}
hr=int(time.time()//3600*3600)
def shape_ok(rec):
    g.hist.clear()
    for i in range(30): g.hist[str(hr-i*3600)]=json.loads(json.dumps(rec))
    try: g.metrics(); return True
    except Exception: return False
fails=[k for k in FULL if not shape_ok({a:b for a,b in FULL.items() if a!=k})]
check(not fails, f"history is built with any one key missing {fails}")
random.seed(5)
bad=[n for n in range(60) if not shape_ok({k:FULL[k] for k in random.sample(list(FULL), random.randint(0,len(FULL)))})]
check(not bad, "and with random sets of keys missing")
check(shape_ok({**FULL,"h":None,"fh":None,"ch":None}), "and with empty nested values")
srv.shutdown()
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
