from harness import *
g=guard(mock())
g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":32}
a=g.airtime_ms(60)
check("airtime of a 60-byte packet at SF8/62.5k/CR8 is about 0.7 s", 600<a<800, a)
g.radio={"spreading_factor":11,"bandwidth":250000,"coding_rate":5,"preamble_length":16}
check("airtime grows with spreading factor", g.airtime_ms(60)>a*0.5)
g.radio={}; check("unknown radio -> 0, no crash", g.airtime_ms(60)==0)
g.repeaters={"ts":time.time(),"list":[{"key":"82AB","name":"A","seen":2,"lat":51,"lon":0},{"key":"82CD","name":"B","seen":3,"lat":None,"lon":None},{"key":"76EE","name":"C","seen":1,"lat":50,"lon":1}]}
check("repeaters sharing a code all found, newest first", [r["name"] for r in g.repeaters_for("82")]==["B","A"])
check("longer code narrows it", [r["name"] for r in g.repeaters_for("82AB")]==["A"])
check("direct has no repeater", g.repeaters_for("DIRECT")==[])
# counting
g.cfg["mode"]="protect"; g.radio={"spreading_factor":8,"bandwidth":62500,"coding_rate":8,"preamble_length":32}
now=time.time()
g.blocks["hop:76"]={"id":1,"kind":"hop","value":"76","source":"hop","created":now-999,"expires":now+999,"hits":0}
def ev(sender,path,matched=None,random=False,ts=None):
    e=sg.Event(ts or now-200,path,sender,"x","Public"); e.random=random; e.matched=matched; e.length=60; return e
for i,e in enumerate([ev("QX1",["76","04"],"hop:76",True), ev("QX2",["76","04"],None,True), ev("Dave",["44","76"],"hop:76"), ev("Sue",["44"])]):
    e.ts=now-300+i; g._count(e)
m=g.metrics()
check("stopped / let through / genuine held / messages counted", (m["d1"]["c"],m["d1"]["x"],m["d1"]["g"],m["d1"]["m"])==(1,1,1,4), m["d1"])
check("airtime saved counted for stopped spam", m["d1"]["a"]>600)
check("spam source 76 has 2", m["sources"][0]["hop"]=="76" and m["sources"][0]["d7"]==2)
check("stop rate 50%", m["d1"]["stop_rate"]==50)
g.known["QX7TEST"]=[now-90000,now-100,5]
e=ev("QX7TEST",["44"],None,True); e.ts=now-250; g._count(e)
check("an odd-looking name already known from genuine messages isn't counted as spam let through", g.metrics()["d1"]["x"]==1 and g.metrics()["d1"]["m"]==5, g.metrics()["d1"])
g._count(ev("QX9",["76"],None,True,ts=now-400)); check("older than the counted mark: not counted twice", g.metrics()["d1"]["m"]==5)
check("24 hourly and 7 daily points", len(m["hourly"])==24 and len(m["daily"])==7 and len(m["by_hour"])==24)
check("styled name is not 'disguised'", not sg.Event(now,[],"KQZ✝ld","hello there","Public").obfuscated)
check("mentioning a styled name is not 'disguised'", not sg.Event(now,[],"Bob","@[KQZ✝ld] morning","Public").obfuscated)
check("emoji inside a word of the message still is", sg.Event(now,[],"Bob","Bu🔥ilt nothing","Public").obfuscated)
g._save_state(force=True); g2=sg.SpamGuard(dict(g.file_cfg))
check("history survives restart", g2.metrics()["d1"]["m"]==5)
print(f"\n{sum(c for _,c in RESULTS)}/{len(RESULTS)} passed")
