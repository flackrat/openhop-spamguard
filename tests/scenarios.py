from harness import *
SPAM="Totally free unlimited mesh upgrades, message me today to claim yours"

def run(m, g, polls=1):
    for _ in range(polls):
        g.poll_once(); time.sleep(0.05)
    g.last_sync=0; g.sync_pending=True; g.poll_once()   # force any pending sync

print("\n== 1. Baseline: rotating random names, same text, via repeater 27")
m=mock()
for i in range(4): m.add(rname(),SPAM,["6A","D8","7E"],ago=60-i)
g=guard(m); run(m,g)
check("blocks repeater 6A (exact route)", m.decide(rname(),"brand new wording entirely",["6A","D8","7E"])=="drop")
check("same text via unrelated route blocked", m.decide("Someone",SPAM,["44","13"])=="drop")
check("6A mid-route: unknown name held (except-known mode)", m.decide("Dave M","Hello from the hill, any takers for a net tonight?",["44","6A","7E"])=="drop")
g.known["Dave M"]=[time.time()-900,time.time()-600,2]; run(m,g)
check("6A mid-route: known name let through", m.decide("Dave M","Hello from the hill, any takers for a net tonight?",["44","6A","7E"])=="allow")
m2=mock()
for i in range(4): m2.add(rname(),SPAM,["6A","D8","7E"],ago=60-i)
g2=guard(m2,hop_match_mode="exact_paths"); run(m2,g2)
check("exact_paths mode: 6A mid-route not blocked", m2.decide("Dave M","Hello from the hill, any takers for a net tonight?",["44","6A","7E"])=="allow")

print("\n== 2. Lowercase / longer / mixed-case random names")
for n in ["ud6dwrek","xk7qp2mz9","Qx7Tp2Lm","4kd9w2pq7z"]:
    sc=sg.name_score(n,[__import__("re").compile(p,2) for p in sg.DEFAULT_CONFIG["random_name_patterns"]])
    check(f"'{n}' scored as random ({sc})", sc>=3)
for n in ["Bob42","Sarah2","Riverside⚡","Dave M","BOT-01-TEST","HomeRepeater1","G4XYZ Pete","Sarah","M0ABC","Dave1985","ChrisP"]:
    sc=sg.name_score(n,[__import__("re").compile(p,2) for p in sg.DEFAULT_CONFIG["random_name_patterns"]])
    check(f"'{n}' not random at balanced ({sc})", sc<3)

print("\n== 3. Random words added before/after the spam text (defeats exact matching)")
m=mock()
for i in range(4):
    pre=" ".join(random.choice(["hey","lol","ok","so","yo","fyi"]) for _ in range(2))
    m.add(rname(),f"{pre} {SPAM} {random.randint(100,999)}",["5C","9F"],ago=60-i)
g=guard(m); run(m,g)
check("campaign rule from shared text", any(b["source"]=="campaign" for b in g.status()["blocks"]), [b["value"] for b in g.status()["blocks"]])
check("new padded variant blocked", m.decide(rname(),f"wow look {SPAM} 4242",["22","9F"])=="drop")

print("\n== 4. Look-alike letters and hidden characters")
m=mock()
variants=["Tоtally frее unlimited mesh upgrades, message me tоday to claim yours",
          "Totally​ free unlimited​ mesh upgrades, message me today to claim yours",
          "TOTALLY FREE UNLIMITED MESH UPGRADES, MESSAGE ME TODAY TO CLAIM YOURS",
          "T0tally fr33 unl1mited mesh upgrades, message me t0day t0 cla1m y0urs"]
for i,v in enumerate(variants): m.add(["Steve","Mark","Jon","Al"][i],v,["6E","13"],ago=60-i)
g=guard(m); run(m,g); st=g.status()
check("variants grouped as one campaign", st["campaigns"] and st["campaigns"][0]["senders"]==4, st["campaigns"])
check("obfuscated messages flagged", sum(1 for x in st["recent"] if x["obfuscated"])>=2)
check("each variant blocked", all(m.decide("X",v,["77"])=="drop" for v in variants))
check("repeater 6E blocked (campaign senders)", m.decide("Nobody","totally different text here",["6E","13"])=="drop")

print("\n== 5. Slow drip: one random name every 20 minutes")
m=mock()
for i in range(5): m.add(rname(),f"spam {i} "+"".join(random.choice(string.ascii_lowercase) for _ in range(25)),["3D","D8"],ago=6000-i*1200)
g=guard(m); run(m,g)
check("slow spam repeater 3D blocked via long window", "hop:3D" in g.blocks, g.status()["hops"][:2])

print("\n== 6. Realistic human names, unique messages, many names via one repeater")
m=mock()
names=["Dave","Sarah","Mike","Emma","Paul","Kate","Rob","Lucy"]
for i,n in enumerate(names): m.add(n,f"Hi all {''.join(random.choice(string.ascii_lowercase) for _ in range(20))}",["A9","D8"],ago=300-i*20)
g=guard(m); run(m,g)
check("brand-new names all on one route block just that route, not repeater A9", "route:A9>D8" in g.blocks and "hop:A9" not in g.blocks, list(g.blocks))
m=mock()
for i,n in enumerate(names): m.add(n,f"Hi all {''.join(random.choice(string.ascii_lowercase) for _ in range(20))}",["A9",f"B{i%4}"],ago=300-i*20)
g=guard(m); run(m,g)
check("repeater A9 blocked on brand-new names spread over several routes", "hop:A9" in g.blocks and not any(k.startswith("route:") for k in g.blocks), list(g.blocks))
m=mock()
for i,n in enumerate(names): m.add(n,f"Hi all {''.join(random.choice(string.ascii_lowercase) for _ in range(20))}",["A9","D8"],ago=300-i*20)
g=guard(m, hop_prefer_route=False); run(m,g)
check("repeater A9 blocked on brand-new names when route-only blocking is off", "hop:A9" in g.blocks and "route:A9>D8" not in g.blocks, list(g.blocks))
g2=guard(m,sensitivity="relaxed"); run(m,g2)
check("relaxed sensitivity tolerates 8 new names (busy event)", "hop:A9" not in g2.blocks)

print("\n== 7. Genuine traffic is left alone")
m=mock()
legit=[("Riverside⚡","It's the usual crowd 😂",["36","21"]),("Dave M","Morning all",["D8","7E"]),("Dave M","Morning all",["D8","7E"]),
       ("Pete","Morning all",["44"]),("G4XYZ Pete","Testing new antenna on the mast, signal report appreciated",["44","7E"]),
       ("BOT-01-TEST","ACK T-Rx-01, H: 10",["4A","2D"]),("BOT-01-TEST","ACK T-Rx-01, H: 11",["4A","2D"])]
for i,(s_,t,p) in enumerate(legit): m.add(s_,t,p,ago=500-i*30)
g=guard(m); run(m,g)
check("no repeater blocked", not any(b["kind"]=="hop" for b in g.blocks.values()), list(g.blocks))
check("no campaign rule", not any(b["source"]=="campaign" for b in g.blocks.values()), [b["value"] for b in g.blocks.values()])
check("short 'Morning all' from someone else allowed", m.decide("Ann","Morning all",["D8"])=="allow")
check("new genuine message allowed", m.decide("Ann","Anyone fancy a coffee at the station later?",["D8","7E"])=="allow")

print("\n== 8. Spammer copies a trusted name")
m=mock()
for i,n in enumerate(["Riverside⚡",rname(),rname()]): m.add(n,SPAM,["6A","D8"],ago=60-i)
g=guard(m); g.allow_senders.add("Riverside⚡"); run(m,g)
check("campaign still blocked although one name is trusted", m.decide("Riverside⚡",SPAM,["44"])=="drop")

print("\n== 9. Spammer within direct range (no repeaters on route)")
m=mock()
for i in range(4): m.add(rname(),SPAM+f" {i}",[],ago=60-i)
g=guard(m); run(m,g)
check("direct-range warning shown", g.status()["direct_spam"] is not None)
check("text still blocked", m.decide(rname(),SPAM+" 9",[])=="drop")

print("\n== 10. Multibyte path hashes")
m=mock()
for i in range(4): m.add(rname(),f"{SPAM} {i}",["6AAB","D8C4"],ago=60-i)
g=guard(m); run(m,g)
check("2-byte route learnt and blocked", m.decide(rname(),"different words now",["6AAB","D8C4"])=="drop")
g.allow_hops.add("6A"); g.blocks.clear(); g.decide()
check("never-block '6A' also covers '6AAB'", "hop:6AAB" not in g.blocks)

print("\n== 11. Hashtag channel")
m=mock(); key=sg.hashtag_secret("#chat")
for i in range(4): m.add(rname(),SPAM,["6A","D8"],ago=60-i,key=key)
g=guard(m,hashtag_channels=["#chat"]); run(m,g)
check("#chat spam decrypted", g.status()["summary"]["unreadable"]==0)
check("#chat campaign blocked", m.decide(rname(),SPAM,["55"],key=key)=="drop")

print("\n== 12. Flood of unique spam (rule budget)")
m=mock()
for i in range(400): m.add(rname(),f"Unique spam message number {i} with filler {random.random()}",["6A","D8"],ago=500-i)
g=guard(m,max_total_rules=120); run(m,g)
check("rules capped at 120 (+ a few known-people rules)", len(m.policy["policy_engine"]["rules"])<=130, len(m.policy["policy_engine"]["rules"]))
check("your own rule kept", any(r["name"]=="my own rule" for r in m.policy["policy_engine"]["rules"]))
check("repeater block kept despite cap", any(r["name"].startswith("spamguard:hop:6A") for r in m.policy["policy_engine"]["rules"]))

print("\n== 13. Monitor mode and pause")
m=mock()
for i in range(4): m.add(rname(),SPAM,["6A","D8"],ago=60-i)
g=guard(m,mode="monitor"); run(m,g)
check("monitor writes log_only rules", all(r["then"]["action"]=="log_only" for r in m.policy["policy_engine"]["rules"] if r["name"].startswith("spamguard") and "known-people" not in r["name"]))
g.apply_settings({"paused":True})
check("pause removes all SpamGuard rules", not any(r["name"].startswith("spamguard") for r in m.policy["policy_engine"]["rules"]))
g.apply_settings({"paused":False,"mode":"protect"})
check("protect writes drop rules", any(r["then"]["action"]=="drop" for r in m.policy["policy_engine"]["rules"] if r["name"].startswith("spamguard") and "known-people" not in r["name"]))

print("\n== 14. Settings: presets, overrides, validation, restart, legacy state")
g.apply_settings({"sensitivity":"strict"}); check("strict preset applied", g.cfg["hop_random_senders"]==2)
g.apply_settings({"hop_new_senders":9}); check("override kept over preset", g.cfg["hop_new_senders"]==9)
g.apply_settings({"sensitivity":"relaxed"}); check("choosing a preset clears overrides", g.cfg["hop_new_senders"]==10)
try: g.apply_settings({"similarity":5}); check("rejects out-of-range value", False)
except ValueError as e: check("rejects out-of-range value", "between" in str(e))
try: g.apply_settings({"random_name_patterns":"[bad"}); check("rejects bad pattern", False)
except ValueError: check("rejects bad pattern", True)
g._save_state(force=True)
g3=sg.SpamGuard({"state_file":g.cfg["state_file"],"openhop_url":g.cfg["openhop_url"],"api_key":"t"})
check("settings survive restart", g3.cfg["sensitivity"]=="relaxed" and g3.cfg["mode"]=="protect")
json.dump({"settings":{"action":"drop","hop_one_shot_senders":7},"blocks":{"hop:6A":{"kind":"hop","value":"6A","created":time.time(),"expires":time.time()+99,"reason":"x"}}},open(os.path.join(TMP,"legacy.json"),"w"))
g4=sg.SpamGuard({"state_file":os.path.join(TMP,"legacy.json")})
check("v4 state upgraded", g4.cfg["mode"]=="protect" and g4.cfg["hop_new_senders"]==7 and "paths" in g4.blocks["hop:6A"])
cf=sg.load_config(os.path.join(REPO,"config.yaml")); check("beginner config loads", cf["mode"]=="monitor" and cf["sensitivity"]=="balanced")

print("\n== 15. Web actions")
m=mock(); m.add("Ann","Is the town repeater back on air after the storm?",["D8"],ago=30)
g=guard(m); run(m,g)
r=g.action("mark_spam",{"text":"Totally fake spam message for testing purposes here","channel":"Public"})
check("mark as spam creates a rule", m.decide("Z","Totally fake spam message for testing purposes here",["1"])=="drop")
k=[k for k,b in g.blocks.items() if b["source"]=="dedupe"]
g.action("not_spam",{"sender":"Ann","matched":k[0] if k else None})
check("not spam trusts sender and removes rule", "Ann" in g.allow_senders and (not k or k[0] not in g.blocks))
g.action("allow_text",{"text":"net check-in"})
check("text exemption stored", "net check-in" in g.allow_texts)
g.action("add_channel",{"name":"#test"}); check("hashtag channel added from page", "#test" in g.cfg["channels"])
r=g.action("block_hop",{"hop":"0x9f"}); check("manual hop block accepts 0x prefix", "hop:9F" in g.blocks)

print(f"\n{sum(ok for _,ok in RESULTS)}/{len(RESULTS)} passed")
for n,ok in RESULTS:
    if not ok: print("FAILED:",n)
