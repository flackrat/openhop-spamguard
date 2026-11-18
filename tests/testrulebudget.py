# The rule allowance is used efficiently: a rule that an earlier rule of equal or wider reach already covers is left
# out of openHop's list and comes back if the covering rule goes away; a sentence hold that catches nothing is let go
# early and does not come back until the sentence is sent again. All data made up.
import sys, logging
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def texts(g):
    main,tail=g.build_rule_sets()
    out=[]
    for r in main+tail:
        for c in r["if"]["all"]:
            if c.get("field")=="channel_message_body": out.append((r["name"],c["value"]))
    return out
def sentence(g,key,text,ttl=14*86400):
    g._add_block(key,"text",text,"test","campaign",ttl=ttl); g.blocks[key]["gate"]=True
m=mock(); g=guard(m)
g._add_block("text:wide","text","cheap mesh upgrades","test","campaign",ttl=3600)
sentence(g,"sentence:a","buy cheap mesh upgrades today friends")
sentence(g,"sentence:b","something quite different and unrelated here")
t=texts(g)
check(sum("cheap mesh upgrades" in v for _,v in t)==1,"a sentence that contains a held text is not written twice")
check(any("something quite different" in v for _,v in t),"an unrelated sentence is still written")
check(any(n.endswith(("text:wide","text:wide (campaign) text \"cheap mesh upgrades\"")) or "text:wide" in n for n,_ in t),"the wider rule stays")
# the cover goes away: the sentence hold is written again
del g.blocks["text:wide"]
check(any("buy cheap mesh upgrades today" in v for _,v in texts(g)),"it comes back when the covering rule expires")
# a different action or a left-out sender is not covered
g=guard(mock())
g._add_block("text:w2","text","cheap mesh upgrades","test","campaign",ttl=3600)
g.blocks["text:w2"]["sender"]="Somebody"
sentence(g,"sentence:c","buy cheap mesh upgrades today friends")
check(any("buy cheap mesh upgrades today" in v for _,v in texts(g)),"a rule that leaves a sender out covers nothing")
g=guard(mock())
g._add_block("text:w3","text","cheap mesh upgrades","test","campaign",ttl=3600)
g.blocks["text:w3"]["action"]="log_only"
sentence(g,"sentence:d","buy cheap mesh upgrades today friends")
check(any("buy cheap mesh upgrades today" in v for _,v in texts(g)),"a watching rule does not cover a holding one")
# a longer text inside the same list is covered by a shorter one; equal texts are written once
g=guard(mock())
g._add_block("text:s","text","free radio giveaway","test","campaign",ttl=3600)
g._add_block("text:l","text","free radio giveaway.....","test","campaign",ttl=3600)
g._add_block("text:e","text","free radio giveaway","test","campaign",ttl=3600)
check(sum("giveaway" in v for _,v in texts(g))==1,"longer and equal texts in the same list are written once")
# another channel is not covered
g=guard(mock(), channels={"Other":"11"*16})
g._add_block("text:o","text","cheap mesh upgrades","test","campaign",ttl=3600,channel="Other")
sentence(g,"sentence:e","buy cheap mesh upgrades today friends")
check(sum("cheap mesh upgrades" in v for _,v in texts(g))==2,"a rule on another channel does not cover it")
# idle sentence holds are let go early, and not made again until the sentence is sent again
g=guard(mock(), remember_sentences=True)
now=time.time()
sentence(g,"sentence:idle","a long sentence nobody sends any more at all")
g.blocks["sentence:idle"]["created"]=now-3*86400
sentence(g,"sentence:busy","a long sentence that keeps getting caught now")
g.blocks["sentence:busy"]["created"]=now-3*86400; g.blocks["sentence:busy"]["last_hit"]=now-3600
g._expire_blocks(now)
check("sentence:idle" not in g.blocks,"a sentence hold with no catch for two days is let go")
check("sentence:busy" in g.blocks,"one still catching stays")
check("sentence:idle" in g.sentence_quiet,"and is remembered as let go")
g2=guard(mock(), remember_sentences=True)
sentence(g2,"sentence:young","a long sentence made this morning by names")
g2._expire_blocks(now)
check("sentence:young" in g2.blocks,"a new hold is never judged early")
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
