import json, threading, time, hashlib, hmac, random, string, sys, os
import tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPENHOP = os.environ.get("OPENHOP_SRC", os.path.join(REPO, "tests", ".openhop"))
TMP = tempfile.mkdtemp(prefix="sgtest-")
OPENHOP_CORE = os.environ.get("OPENHOP_CORE_SRC", os.path.join(REPO, "tests", ".openhop_core", "src"))
sys.path.insert(0, REPO); sys.path.insert(0, OPENHOP); sys.path.insert(0, OPENHOP_CORE)
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from Crypto.Cipher import AES
import spamguard as sg
from repeater.policy_engine import PolicyEngine
logging=__import__("logging"); logging.basicConfig(level=logging.ERROR)

def enc(sender, text, key=sg.PUBLIC_CHANNEL_KEY):
    k = sg._secret32(key)
    pt = int(time.time()).to_bytes(4,"little") + b"\x00" + f"{sender}: {text}".encode()
    pt += b"\x00" * ((-len(pt)) % 16)
    ct = AES.new(k[:16], AES.MODE_ECB).encrypt(pt)
    return (bytes([sg.channel_hash_byte(key)]) + hmac.new(k, ct, hashlib.sha256).digest()[:2] + ct).hex()

class Mock:
    def __init__(self, port):
        self.packets=[]; self.policy={"policy_engine":{"enabled":True,"default_action":"allow","rules":[
            {"id":1,"name":"my own rule","enabled":True,"if":{"field":"hop_count","op":"equals","value":99},"then":{"action":"drop"}}],"objects":{}},"groups":{}}
        self.posts=0; m=self; self.filtered=True; self.filtered_calls=0; self.recent_calls=0; self.plugins=None  # optional handler for openHop's /api/plugins endpoints
        class H(BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def do_GET(self):
                from urllib.parse import urlparse, parse_qs
                u=urlparse(self.path); q={k:v[0] for k,v in parse_qs(u.query).items()}
                if u.path.startswith("/api/plugins"):
                    if not m.plugins: self.send_response(404); self.end_headers(); return
                    return m.plugins(self, "GET", u.path, q)
                if "filtered_packets" in u.path:
                    if not m.filtered:
                        self.send_response(404); self.end_headers(); return
                    m.filtered_calls+=1; m.last_q=q
                    rows=[p for p in m.packets if ("type" not in q or p["type"]==int(q["type"]))
                          and ("start_timestamp" not in q or p["timestamp"]>=float(q["start_timestamp"]))]
                    rows=sorted(rows,key=lambda p:-p["timestamp"])[:int(q.get("limit",1000))]
                    d={"success":True,"data":rows}
                elif "recent_packets" in u.path:
                    m.recent_calls+=1
                    d={"success":True,"data":sorted(m.packets,key=lambda p:-p["timestamp"])[:int(q.get("limit",100))]}
                else:
                    d={"success":True,"data":m.policy}
                b=json.dumps(d).encode(); self.send_response(200); self.end_headers(); self.wfile.write(b)
            def do_POST(self):
                if self.path.startswith("/api/plugins"):
                    if not m.plugins: self.send_response(404); self.end_headers(); return
                    return m.plugins(self, "POST", self.path.split("?")[0], {})
                body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                m.policy["policy_engine"]=body["policy_engine"]; m.posts+=1
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')
        self.srv=ThreadingHTTPServer(("127.0.0.1",port),H); threading.Thread(target=self.srv.serve_forever,daemon=True).start()
    def add(self, sender, text, path, ago=0, key=sg.PUBLIC_CHANNEL_KEY):
        self.packets.append({"id":len(self.packets)+1,"timestamp":time.time()-ago,"type":5,"payload":enc(sender,text,key),
            "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})
    def decide(self, sender, text, path, key=sg.PUBLIC_CHANNEL_KEY):
        class P:
            def __init__(s): s.payload=bytearray(bytes.fromhex(enc(sender,text,key))); s.transport_codes=[0,0]
            def get_path_hashes_hex(s): return path
            def get_payload_type(s): return 5
            def get_payload(s): return s.payload
        return PolicyEngine(self.policy["policy_engine"]).evaluate(P(),{"payload_type":5,"hop_count":len(path)}).action

PORT=[18100]
def guard(m, **over):
    st=os.path.join(TMP, f"state_{PORT[0]}.json")
    if os.path.exists(st): os.remove(st)
    # Most tests were written when one message made a name "known"; they test other things, so keep that.
    cfg={"openhop_url":f"http://127.0.0.1:{m.srv.server_address[1]}","api_key":"t","mode":"protect","state_file":st,
         "known_min_msgs":1,"known_min_minutes":0,"vary_limits":False}
    cfg.update(over); return sg.SpamGuard(cfg)
def mock():
    PORT[0]+=1; return Mock(0)
def rname(n=8, lower=False):
    # A made-up name in the style the spammer uses. Re-rolled on the rare chance it comes out looking
    # like a device's default name (all hex), which SpamGuard deliberately counts for less.
    while True:
        s="".join(random.choice(string.ascii_uppercase+string.digits) for _ in range(n-1))+random.choice(string.digits)
        if not (n == 8 and all(c in "0123456789ABCDEF" for c in s)):
            return s.lower() if lower else s
RESULTS=[]
def check(name, cond, detail=""):
    RESULTS.append((name,bool(cond))); print(("PASS " if cond else "FAIL ")+name+(("  -- "+str(detail)) if detail and not cond else ""))
