from harness import *
SPAM="Totally free unlimited mesh upgrades, message me today to claim yours"
def run(m,g,polls=1):
    for _ in range(polls): g.poll_once(); time.sleep(0.05)
    g.last_sync=0; g.sync_pending=True; g.poll_once()
for W,name in [(2,"2-byte"),(3,"3-byte")]:
    h=lambda s: (s*3)[:2*W]
    P=[h("6A"),h("D8"),h("7E")]
    print(f"\n== {name} paths: {P}")
    m=mock()
    for i in range(4): m.add(rname(),SPAM,P,ago=60-i)
    g=guard(m); run(m,g)
    check(f"{name}: spam text blocked on any route", m.decide("Someone",SPAM,[h("44"),h("13")])=="drop")
    check(f"{name}: new spam via the same exact route blocked", m.decide(rname(),"totally new words here please",P)=="drop")
    check(f"{name}: unknown name through spam repeater held", m.decide("Dave M","Hello from the hill, any takers?",[h("44"),P[0],P[2]])=="drop")
    g.known["Dave M"]=[time.time()-900,time.time()-600,1]; run(m,g)
    check(f"{name}: known name through spam repeater allowed", m.decide("Dave M","Hello from the hill, any takers?",[h("44"),P[0],P[2]])=="allow")
    check(f"{name}: genuine chat 1-byte allowed", m.decide("Dave M","Hello from the hill, any takers?",["44","13"])=="allow")
    rules=m.policy["policy_engine"]["rules"]
    bad=[r["name"] for r in rules for c in r["if"].get("all",[]) if c["field"]=="path_hashes" and isinstance(c["value"],list) and len({len(x) for x in c["value"]})>1]
    check(f"{name}: no rule mixes hop widths", not bad, bad)
    st=g.status(); check(f"{name}: status/page builds", isinstance(st,dict) and st.get("hops") is not None)
print("\n== width switch: spammer learns 2-byte block, then sends 1-byte")
m=mock()
for i in range(6): m.add(rname(),f"random junk {i} "+rname(12),["6AAB","D8C2","7E01"],ago=300-i*30)
g=guard(m); run(m,g)
print("  blocks:",[ (k,b.get('source')) for k,b in g.blocks.items()])
print("  1-byte same repeater:", m.decide(rname(),"some fresh junk text abc",["6A","D8","7E"]))
print("  2-byte same route:", m.decide(rname(),"some fresh junk text abc",["6AAB","D8C2","7E01"]))
print("\n== allow-list 1-byte hop vs 2-byte traffic")
g.allow_hops.add("6A"); print("  hop_allowed('6AAB'):", g.hop_allowed("6AAB"))
print(f"\n{sum(c for _,c in RESULTS)}/{len(RESULTS)} passed")
