# Emoji reactions some companion apps send as text ("@[Name]" + emoji, a new line, an 8-character code worked out
# from the message reacted to). A reaction whose code matches a message heard here is not counted as a repeat; a
# made-up code, a slogan in the brackets, or a reaction to something never heard here is judged as ordinary text.
# Reactions still count towards a name's message budget. All names and messages are made up.
import sys, os, json, logging, time, hashlib, struct
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)

# the code, worked out the way the app does, independently of SpamGuard
def app_code(text, sent):
    d=hashlib.sha256(text.encode()+struct.pack("<I",sent)).digest()[:5]; n=int.from_bytes(d,"big")
    return "".join("0123456789abcdefghjkmnpqrstvwxyz"[(n>>(35-5*i))&31] for i in range(8))
check(sg.reaction_code("Morning all, frosty on the ridge",1764000000)==app_code("Morning all, frosty on the ridge",1764000000),"same code as the app")
check(sg.reaction_parts("@[Pat Quill]👍\nb45pc4ek")==("Pat Quill","👍","b45pc4ek"),"the channel form")
check(sg.reaction_parts("👍@[Pat Quill]\nB45PC4EK")==("Pat Quill","👍","b45pc4ek"),"the older emoji-first form, either case")
check(sg.reaction_parts("@[Pat Quill]👍🏽\nb45pc4ek") is not None,"a skin tone")
check(sg.reaction_parts("@[Pat Quill]❤️\nb45pc4ek") is not None,"a variation selector")
check(sg.reaction_parts("@[Pat Quill]👨‍👩‍👧\nb45pc4ek") is not None,"a joined emoji")
check(sg.reaction_parts("@[Pat Quill]ok\nb45pc4ek") is None,"words are not an emoji")
check(sg.reaction_parts("@[Pat Quill]👍 thanks\nb45pc4ek") is None,"nothing else in the message")
check(sg.reaction_parts("@[Pat Quill]👍\nb45pc4ek extra") is None,"nothing after the code")
check(sg.reaction_parts("@[Pat Quill]👍\nb45pc4eu") is None,"letters outside the code alphabet")
check(sg.reaction_parts("@[VISIT QUARRYTOWN NET FOR THE BEST DEALS NOW]👍\nb45pc4ek") is None,"a slogan too long for a name")

def add(m, sender, text, path, ago, sent_off=3):
    ts=time.time()-ago
    m.packets.append({"id":len(m.packets)+1,"timestamp":ts,"type":5,"payload":enc(sender,text,sent=int(ts)-sent_off),
                      "packet_hash":os.urandom(8).hex(),"original_path":json.dumps(path)})
    return int(ts)-sent_off
def cycle(g):
    for _ in range(3):
        g.poll_once(); g.last_sync=0; g.sync_pending=True

m=mock(); g=guard(m, known_min_msgs=2, slow_repeat_max=2, quick_resend_hold=True)
for i in range(3): add(m,"Ren Tally",f"Afternoon from the valley, number {i}",["A1","B2"],ago=6000-i*100)
targets=[("Pat Quill",f"Club net tonight at eight, topic number {i}") for i in range(6)]
sents=[add(m,w,t,["C3","B2"],ago=5000-i*500) for i,(w,t) in enumerate(targets)]
cycle(g)
# Ren reacts with the same emoji to six of Pat's messages: same text each time, different code
for i,((w,t),s) in enumerate(zip(targets,sents)):
    add(m,"Ren Tally",f"@[{w}]👍\n{app_code(t,s)}",["A1","B2"],ago=2200-i*200)
cycle(g)
ren=[e for e in g.events if e.sender=="Ren Tally" and e.text.startswith("@[")]
check(len(ren)==6 and all(e.reaction for e in ren),"all six reactions check out: %s"%[bool(e.reaction) for e in ren])
check(ren and ren[0].reaction=={"to":"Pat Quill","emoji":"👍"},"what it reacted to")
check(not any(e.matched for e in ren),"none held: %s"%[e.matched for e in ren])
check(not any(b.get("source") in ("repeat","slow") or "Ren" in json.dumps(b) for b in g.blocks.values()),
      "no repeat hold made: %s"%[(b.get("source"),b.get("value")) for b in g.blocks.values()])
check(g.stats.get("reactions",0)>=6,"counted")

# a clock a second out still checks out
add(m,"Ren Tally",f"@[Pat Quill]🎉\n{app_code(targets[0][1],sents[0]+1)}",["A1","B2"],ago=200); cycle(g)
check(g.events[-1].reaction,"a second of rounding is allowed")

# made-up codes from another name, the same shape: judged as before (the disguise check still holds them)
m2=mock(); g2=guard(m2, known_min_msgs=2, slow_repeat_max=2)
for i in range(3): add(m2,"Sly Dunmore",f"Hello from the hill number {i}",["D4","B2"],ago=9000-i*100)
for i,(w,t) in enumerate(targets[:3]): add(m2,w,t,["C3","B2"],ago=8000-i*600)
cycle(g2)
fake=["qa7mz3kw","pq4xt8vn","hj2wq6ry","bn5ke9ad","wc3yf7rp","k2m9x4qa"]
for i,cd in enumerate(fake[:3]): add(m2,"Sly Dunmore",f"@[Pat Quill]🤡\n{cd}",["D4","B2"],ago=1500-i*200)
cycle(g2)
for b in g2.blocks.values(): b["created"]=time.time()-1000
for i,cd in enumerate(fake[3:]): add(m2,"Sly Dunmore",f"@[Pat Quill]🤡\n{cd}",["D4","B2"],ago=420-i*60)
cycle(g2)
sly=[e for e in g2.events if e.sender=="Sly Dunmore" and e.text.startswith("@[")]
check(not any(e.reaction for e in sly),"made-up codes are not trusted")
check(any(e.matched for e in sly[3:]),"and are still held as repeats: %s"%[e.matched for e in sly])

# a reaction to a message never heard here: ordinary text
m3=mock(); g3=guard(m3)
add(m3,"Ren Tally",f"@[Pat Quill]👍\n{app_code('something we never heard',1764000000)}",["A1"],ago=100); cycle(g3)
check(g3.events and not g3.events[-1].reaction,"target not heard here: not a verified reaction")
# a reaction naming the wrong person doesn't check out either
m4=mock(); g4=guard(m4)
s4=add(m4,"Pat Quill","Anyone on the ridge tonight",["C3"],ago=500)
add(m4,"Ren Tally",f"@[Kit Wren]👍\n{app_code('Anyone on the ridge tonight',s4)}",["A1"],ago=100); cycle(g4)
check(not g4.events[-1].reaction,"named the wrong person")
add(m4,"Ren Tally",f"@[Pat Quill]👍\n{app_code('Anyone on the ridge tonight',s4)}",["A1"],ago=50); cycle(g4)
check(g4.events[-1].reaction,"named the right person")

# reactions still count towards the per-name budget
m5=mock(); g5=guard(m5, name_budget=True, name_budget_max=8)
ts5=[add(m5,"Pat Quill",f"Net report line {i} from the ridge",["C3"],ago=590-i) for i in range(20)]
for i in range(20): add(m5,"Flo Bramble",f"@[Pat Quill]👍\n{app_code(f'Net report line {i} from the ridge',ts5[i])}",["E5"],ago=500-i*5)
cycle(g5)
flo=[e for e in g5.events if e.sender=="Flo Bramble"]
check(all(e.reaction for e in flo),"budget test reactions verified")
check(any(b.get("source")=="budget" or "Flo" in str(b.get("value")) for b in g5.blocks.values()),
      "a flood of reactions still meets the budget: %s"%[(b.get("source"),b.get("value")) for b in g5.blocks.values()])

print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
