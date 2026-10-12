# Made-up demo data shared by the browser tests. No real messages or names.
import sys, asyncio, threading, os, logging, random, time
from harness import *
from playwright.async_api import async_playwright
logging.disable(logging.WARNING)
random.seed(7)
m=mock()
# made-up regulars
for i,(n,t) in enumerate([("Hilltop Hiker","Morning all, clear skies up here"),("Canal Boat Ted","Anyone hearing me from the lock?"),("Base Camp 3","Radio check please"),("Sparky Sue","Copy that, loud and clear")]):
    m.add(n,t,["A7","2F"],ago=1500-i*120)
# made-up spam campaign under random names through repeater 76
for i in range(6): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D","E1"],ago=60-i)
g=guard(m, listen_port=18171, listen_host="127.0.0.1"); g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
for i in range(4): m.add(rname(),"FREE PRIZE claim now https://spam.example/"+rname(5),["C4","9D","E1"]); 
g.poll_once()
# synthetic history: 7 days of made-up hourly counts
now=int(time.time())//3600*3600; h={}
for k in range(24*7):
    t=now-k*3600; hr=time.localtime(t).tm_hour
    msgs=random.randint(2,9)+(6 if 7<=hr<=22 else 0)
    burst=(18<=hr<=23) and random.random()<0.55
    c=random.randint(3,14) if burst else (1 if random.random()<0.08 else 0)
    x=1 if (c and random.random()<0.15) else 0
    tm=random.randint(0,min(4,msgs)); tc=min(c,random.randint(0,2)) if c else 0
    h[str(t)]={"m":msgs+c+x,"c":c,"x":x,"g":1 if random.random()<0.02 else 0,"a":c*706.0,"h":{"C4":c} if c else {},
               "ch":{"Public":{"m":msgs-tm+c-tc+x,"c":c-tc,"x":x},"#trailchat":{"m":tm+tc,"c":tc}}}
g.hist=h
g.extra_channels["#trailchat"]=sg.hashtag_secret("trailchat"); g.rebuild_cfg()
g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":32}
g.me={"name":"Example Repeater","hash":"5A","lat":0,"lon":0}
g.repeaters={"ts":time.time()+1e9,"list":[{"key":"C4AB12","name":"Ridgeway Relay","seen":time.time(),"lat":0,"lon":0}]}
srv=sg.QuietServer(("127.0.0.1",18171), sg.make_handler(g)); threading.Thread(target=srv.serve_forever,daemon=True).start()
