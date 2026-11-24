# The page decides who may use it from the address of the real network connection, not from anything the visitor
# says. Real sockets on this machine only: a connection from a second loopback address, and (where the machine has
# IPv6) one over IPv6 loopback. A connection from the open internet can't be made inside a test machine; the address
# rules themselves are covered in testwebpeer.py.
import json, socket, threading, http.client, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

m=mock(); g=guard(m, floodguard=False)
H=sg.make_handler(g)
srv=sg.QuietServer(("0.0.0.0",0),H); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
def get(src, host="127.0.0.1", hdr=None):
    c=http.client.HTTPConnection(host,port,timeout=10,source_address=(src,0))
    c.request("GET","/status",headers=hdr or {}); r=c.getresponse(); r.read(); c.close(); return r.status
seen=[]
real=sg.peer_is_local
sg.peer_is_local=lambda a,extra=(): (seen.append(a), real(a,extra))[1]
try:
    st=get("127.0.0.2")
    check(st==200 and seen and seen[-1]=="127.0.0.2","the decision uses the connection's own address: %s %s"%(st,seen[-1:]))
    sg.peer_is_local=lambda a,extra=(): (seen.append(a), a!="127.0.0.2" and real(a,extra))[1]
    check(get("127.0.0.2",hdr={"Host":"127.0.0.1"})==403,"refusing that address refuses it, whatever the Host header says")
    check(get("127.0.0.3")==200,"another address on the same machine is unaffected")
finally:
    sg.peer_is_local=real
srv.shutdown()

# IPv6 loopback, where available
if socket.has_ipv6:
    class V6(sg.QuietServer): address_family=socket.AF_INET6
    try:
        s6=V6(("::1",0),H); p6=s6.server_address[1]
        threading.Thread(target=s6.serve_forever,daemon=True).start()
        c=http.client.HTTPConnection("::1",p6,timeout=10); c.request("GET","/status"); r=c.getresponse(); r.read(); c.close()
        check(r.status==200,"IPv6 loopback is local")
        s6.shutdown()
    except OSError:
        print("note: no IPv6 loopback on this machine, skipped")
print(f"{ok} passed, {fail} failed"); import sys; sys.exit(1 if fail else 0)
