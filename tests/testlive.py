# openHop's live packet feed: SpamGuard opens /ws/packets with its token, answers openHop's pings,
# and is woken to check straight away when a packet is broadcast. A refusal falls back to the timer.
import sys, socket, threading, json, struct, time
from harness import *
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

def frame(obj, op=1):
    p=json.dumps(obj).encode() if not isinstance(obj,bytes) else obj
    n=len(p); return bytes([0x80|op])+(bytes([n]) if n<126 else bytes([126])+struct.pack(">H",n))+p
def read_client_frame(c):
    h=c.recv(2); n=h[1]&0x7F
    if n==126: n=struct.unpack(">H",c.recv(2))[0]
    mask=c.recv(4); d=b""
    while len(d)<n: d+=c.recv(n-len(d))
    return h[0]&0x0F, bytes(b^mask[i%4] for i,b in enumerate(d)), bool(h[1]&0x80)

seen={}
def server(sock, refuse=False):
    c,_=sock.accept(); req=b""
    while b"\r\n\r\n" not in req: req+=c.recv(1024)
    seen["req"]=req.decode()
    if refuse:
        c.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"); c.close(); return
    c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: x\r\n\r\n")
    c.sendall(frame({"type":"ping"}))
    seen["pong"]=read_client_frame(c)
    c.sendall(frame(b"hi",op=9))
    seen["pong2"]=read_client_frame(c)
    time.sleep(0.2); c.sendall(frame({"type":"stats","data":{}}))
    time.sleep(0.3); seen["woke_on_stats"]=g.wake.is_set()
    big={"type":"packet","data":{"payload":"x"*300}}
    c.sendall(frame(big)); time.sleep(0.5); seen["woke"]=g.wake.is_set()
    c.sendall(frame(b"",op=8)); time.sleep(0.3); c.close()

m=mock(); g=guard(m)
s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(1); port=s.getsockname()[1]
g.cfg["openhop_url"]=f"http://127.0.0.1:{port}"; g.cfg["api_key"]="tok-live"
threading.Thread(target=server,args=(s,),daemon=True).start()
stop=threading.Event(); t=threading.Thread(target=g.live_feed_loop,args=(stop,),daemon=True); t.start()
time.sleep(2.5)
check("GET /ws/packets HTTP/1.1" in seen.get("req",""),"asks for /ws/packets")
check("X-API-Key: tok-live" in seen.get("req",""),"sends the API token")
check(seen.get("pong",(0,b"",0))[1]==b'{"type": "pong"}' and seen["pong"][2],"answers openHop's ping with a masked pong")
check(seen.get("pong2",(0,))[0]==10 and seen["pong2"][1]==b"hi","answers a protocol ping")
check(seen.get("woke_on_stats") is False,"stats messages don't wake the check")
check(seen.get("woke") is True,"a broadcast packet wakes the check")
check(g.live["packets"]==1,"counts packets heard live: "+str(g.live))
check(g.live["state"]=="reconnecting","after openHop closes the feed it waits to reconnect: "+g.live["state"])
stop.set()
# An openHop without the feed (or refusing the token): fall back to the timer quietly
g2=guard(mock()); s2=socket.socket(); s2.bind(("127.0.0.1",0)); s2.listen(1)
g2.cfg["openhop_url"]=f"http://127.0.0.1:{s2.getsockname()[1]}"
threading.Thread(target=server,args=(s2,True),daemon=True).start()
stop2=threading.Event(); threading.Thread(target=g2.live_feed_loop,args=(stop2,),daemon=True).start(); time.sleep(1)
check(g2.live["state"]=="unavailable","no feed: marked unavailable, timer carries on")
check(g2.health()["live_feed"]=="unavailable","health reports the feed state")
stop2.set()
# Turned off in settings
g3=guard(mock()); g3.cfg["live_feed"]=False; stop3=threading.Event()
threading.Thread(target=g3.live_feed_loop,args=(stop3,),daemon=True).start(); time.sleep(0.3)
check(g3.live["state"]=="off","setting off: no connection"); stop3.set()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
