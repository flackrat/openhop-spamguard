# Replay guard: a device sending other people's old channel messages out again (broken firmware, an old
# clock, names cut short) has its further copies held back. A person re-sending their own message, the
# mesh's own echoes and short replies are untouched. Checked with openHop's rule engine. All made up.
import sys, logging
from harness import *
from Crypto.Cipher import AES
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def enc_at(sender, text, sent, key=sg.PUBLIC_CHANNEL_KEY):
    k=sg._secret32(key)
    pt=int(sent).to_bytes(4,"little")+b"\x00"+f"{sender}: {text}".encode(); pt+=b"\x00"*((-len(pt))%16)
    ct=AES.new(k[:16],AES.MODE_ECB).encrypt(pt)
    return (bytes([sg.channel_hash_byte(key)])+hmac.new(k,ct,hashlib.sha256).digest()[:2]+ct).hex()
def add(m, sender, text, ago, sent=None, path=("4C","2F")):
    now=time.time()
    m.packets.append({"id":len(m.packets)+1,"timestamp":now-ago,"type":5,"payload":enc_at(sender,text,now-ago if sent is None else sent),
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(list(path))})
def sync(g): g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
OLD=time.time()-823*86400      # a clock 823 days slow

m=mock(); g=guard(m, floodguard=False, known_min_msgs=3, dedupe_enabled=False)   # duplicates under other names have their own guard
add(m,"Quarry Pete","Road closed at the bridge until tonight",ago=900)
add(m,"Quarry Pete","Road closed at the bridge until tonight",ago=600,sent=OLD)     # replayed, old clock
sync(g)
rb=[b for b in g.blocks.values() if b.get("source")=="replay"]
check(len(rb)==1 and rb[0]["who"]=="Quarry Pete","a copy with a badly wrong clock is a replay")
check(m.decide("Quarry Pete","Road closed at the bridge until tonight",["9D","2F"])=="drop","further copies are held back")
check(m.decide("Quarry Pete","Anyone fancy a coffee at the lock?",["4C","2F"])=="allow","anything new from that name still goes out")
check(m.decide("Canal Boat Ted","Road closed at the bridge until tonight",["4C","2F"])=="allow","the same text from someone else isn't caught by it")

# name cut short (the device keeps only 23 bytes of the name), clock fine
m2=mock(); g2=guard(m2, floodguard=False, dedupe_enabled=False)
add(m2,"Hilltop Hiker Portable 2","Net starts at eight on the usual channel",ago=900)
add(m2,"Hilltop Hiker Portabl","Net starts at eight on the usual channel",ago=300,sent=time.time()-300+7)
sync(g2)
check(any(b.get("source")=="replay" and b["who"]=="Hilltop Hiker Portabl" for b in g2.blocks.values()),"a copy under a cut-short name is a replay")
check(m2.decide("Hilltop Hiker Portable 2","Net starts at eight on the usual channel",["4C","2F"])=="allow","the real person's own message isn't held")

# not replays
m3=mock(); g3=guard(m3, floodguard=False)
add(m3,"Sparky Sue","Is anyone hearing me from the harbour?",ago=900)
add(m3,"Sparky Sue","Is anyone hearing me from the harbour?",ago=300)                 # she asks again, clock right
add(m3,"Base Camp 3","Radio check from the top car park please",ago=500)
add(m3,"Base Camp 3","Radio check from the top car park please",ago=492,sent=time.time()-500)  # mesh echo, seconds later
add(m3,"Dave M","ok thanks",ago=800); add(m3,"Dave M","ok thanks",ago=200,sent=OLD)    # too short to judge
sync(g3)
check(not any(b.get("source")=="replay" for b in g3.blocks.values()),
      f"re-asking, the mesh's own echoes and short replies aren't replays: {[b.get('who') for b in g3.blocks.values() if b.get('source')=='replay']}")

# replayed copies don't teach SpamGuard that a name is genuine
m4=mock(); g4=guard(m4, floodguard=False, known_min_msgs=3)
add(m4,"Lighthouse Lou","Fog coming in fast over the point now",ago=1200)
for i in range(4):
    add(m4,"Lighthouse Lou","Fog coming in fast over the point now",ago=900-i*100,sent=OLD)
sync(g4)
check(g4.sender_history["Lighthouse Lou"]["count"]==1,"replayed copies don't count towards knowing a name")
check(g4.stats.get("replays",0)>=1,"replays are counted")

# off
m5=mock(); g5=guard(m5, floodguard=False, replay_guard=False)
add(m5,"Quarry Pete","Road closed at the bridge until tonight",ago=900)
add(m5,"Quarry Pete","Road closed at the bridge until tonight",ago=600,sent=OLD)
sync(g5)
check(not any(b.get("source")=="replay" for b in g5.blocks.values()),"off: nothing is held")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
