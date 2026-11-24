# The 6.48 additions in a browser: device names on People, the airtime breakdown and openHop's advert limit on
# FloodGuard's page, a reaction in Messages and the new Health readings. Desktop and phone, light and dark, with an
# axe scan of each page. Made-up demo data. Saves screenshots when SHOTS is set.
import os, json, struct
SRC=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"demo_setup.py")).read().replace("18171","18193")
exec(SRC)
from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXE=open(os.environ.get("AXE_JS", os.path.join(REPO,"tests",".axe","node_modules","axe-core","axe.min.js"))).read()
SHOTS=os.environ.get("SHOTS")
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
# a device that renamed itself, and a name two devices use
def adv(name, k, ts):
    pub=k.public_key().export_key(format="raw"); app=bytes([0x81])+name.encode(); t=struct.pack("<I",int(ts))
    return (pub+t+eddsa.new(k,"rfc8032").sign(pub+t+app)+app).hex()
k1=ECC.generate(curve="Ed25519"); k2=ECC.generate(curve="Ed25519")
T=time.time()
for name,k,ago in (("Hilltop Hiker",k1,900),("Hilltop Mobile",k1,600),("Hilltop Hiker",k1,300),("Sparky Sue",k2,500)):
    g.learn_advert({"payload":adv(name,k,T-ago),"timestamp":T-ago,"original_path":"[]"})
k3=ECC.generate(curve="Ed25519"); g.learn_advert({"payload":adv("Sparky Sue",k3,T-200),"timestamp":T-200,"original_path":"[]"})
# airtime breakdown: channel traffic, a poller, anonymous requests, two radios
def pk(ts,path,pt,ln,pl="",radio=None):
    p={"id":os.urandom(6).hex(),"timestamp":ts,"type":pt,"route":1,"length":ln,"rssi":-100,"snr":2,"packet_hash":os.urandom(8).hex(),
       "original_path":json.dumps(path),"payload":pl}
    if radio: p["rx_radio_id"]=radio
    return p
ps=[pk(T-3000+i*40,[["A7","C4","2F"][i%3]],5,80,radio=["radio-1","radio-2"][i%2]) for i in range(60)]
ps+=[pk(T-2400+i*60,["7D"],0,30,"5AC4"+"00"*20,radio="radio-1") for i in range(30)]
ps+=[pk(T-2000+i*45+(i%4)*17,["7D"],7,60,"5A"+"AB12CD34"+"00"*40,radio="radio-1") for i in range(14)]
for p in ps: g._kind_note(p,p["type"]); g.fg_observe(p)
import random as _r
for k in range(24):   # a day of made-up airtime by kind
    hk=str(int(T//3600*3600)-k*3600); hh=g.hist.setdefault(hk,{"m":0,"c":0,"x":0,"g":0,"a":0.0,"h":{}})
    hh["kt"]={"5":[60,_r.randint(20,60)*1000],"0":[30,_r.randint(5,25)*1000],"7":[10,(_r.randint(30,90) if 18<=k<=20 else 3)*1000],"4":[200,_r.randint(10,30)*1000],"3":[50,4000],"9":[3,800],"1":[20,6000]}
g.cfg["source_holds"]="watch"
g.source_watch["ptype:7:7D"]={"ptype":7,"hop":"7D","packets":120,"share":48,"busy":31,"label":"anonymous requests","first":T-900,"last":T-600,"times":1,"watch":True}
g.oh_adverts={"available":True,"on":False,"penalty":True,"per_hours":10.0,"burst":2,"allowed":930,"dropped":41,"penalties":1}
g._bd_cache=None
# a verified reaction in Messages
s0=int(T-400); g.heard_recent.setdefault("Public",__import__("collections").deque(maxlen=200)).append(("Canal Boat Ted","Anyone hearing me from the lock?",s0,T-400))
txt="Anyone hearing me from the lock?"
code=sg.reaction_code(txt,s0)
m.packets.append({"id":len(m.packets)+1,"timestamp":time.time(),"type":5,"payload":enc("Sparky Sue",f"@[Canal Boat Ted]👍\n{code}",sent=int(T-100)),"packet_hash":os.urandom(8).hex(),"original_path":json.dumps(["A7","2F"])})
g.poll_once()
check(any(e.reaction for e in g.events),"the demo reaction checked out")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for scheme in ("light","dark"):
            for vp in ({"width":1280,"height":900},{"width":375,"height":800}):
                tag=f"{scheme}-{vp['width']}"
                ctx=await b.new_context(viewport=vp,color_scheme=scheme); pg=await ctx.new_page()
                errs=[]; pg.on("pageerror",lambda x:errs.append(str(x)))
                async def scan(name):
                    await pg.add_script_tag(content=AXE)
                    v=await pg.evaluate("""async()=>(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
                    check(not v,f"{tag} {name}: axe finds nothing: {v}")
                    wide=await pg.evaluate("document.documentElement.scrollWidth>window.innerWidth+1")
                    check(not wide,f"{tag} {name}: nothing wider than the screen")
                # FloodGuard
                await pg.goto("http://127.0.0.1:18193/#/floodguard"); await pg.wait_for_timeout(1800)
                t=await pg.inner_text("#airKindSec")
                check("Requests" in t and "Anonymous requests" in t and "Channel messages" in t,f"{tag}: kinds listed")
                check("every 60 s" in t and "this repeater" in t,f"{tag}: polling to this repeater shown")
                check("AB12CD34" in t,f"{tag}: anonymous requests by key")
                check(await pg.locator("#airKindSec .donut").count()==2,f"{tag}: two doughnuts, by kind and by way in")
                check(await pg.locator("#airKindSec .worth button").count()>=1,f"{tag}: something worth a look")
                # drill into anonymous requests, then across to the repeater it came through, then back
                await pg.locator("#airKindSec .dleg button",has_text="Anonymous requests").first.click(); await pg.wait_for_timeout(400)
                d=await pg.inner_text("#airKindSec")
                check("By sender key" in d and "AB12CD34" in d and "Came in through" in d,f"{tag}: the anonymous requests drill-down")
                check(await pg.evaluate("document.activeElement&&document.activeElement.hasAttribute('data-airfocus')"),f"{tag}: focus moves to the new heading")
                check(await pg.locator("#chartAirOne svg").count()==1,f"{tag}: with its own hourly chart")
                await scan("FloodGuard drill-down")
                if SHOTS: await pg.locator("#airKindSec").screenshot(path=f"{SHOTS}/floodguard-drill-kind-{tag}.png")
                await pg.locator("#airKindSec .hbar",has_text="7D").first.click(); await pg.wait_for_timeout(400)
                d=await pg.inner_text("#airKindSec")
                check("What it carried" in d and "Through" in d,f"{tag}: across to the repeater")
                if SHOTS: await pg.locator("#airKindSec").screenshot(path=f"{SHOTS}/floodguard-drill-entry-{tag}.png")
                await pg.locator("#airKindSec .crumb button").click(); await pg.wait_for_timeout(400)
                check(await pg.locator("#airKindSec .donut").count()==2,f"{tag}: and back")
                segs=await pg.eval_on_selector_all("#chartAirKind path","s=>[...new Set(s.map(x=>x.getAttribute('class')))].sort()")
                check({"k0","k1","k2","k3","k5"}<=set(segs),f"{tag}: the 24-hour chart has a colour per kind and Other: {segs}")
                leg=await pg.eval_on_selector_all("#airKindLegend span","s=>s.map(x=>x.textContent)")
                heads=await pg.eval_on_selector_all("#chartAirKind + details th","s=>s.map(x=>x.textContent)")
                check(len(heads)==1+len(leg),f"{tag}: a table column per legend entry: {heads} {leg}")
                check("By radio" in t and "radio-2" in t,f"{tag}: two radios shown")
                check("would hold" in t,f"{tag}: the watch-only congestion hold shown")
                check(not await pg.is_hidden("#ohAdvSec") and "stopped 41" in await pg.inner_text("#ohAdvSec"),f"{tag}: openHop's advert limit shown")
                await scan("FloodGuard")
                if SHOTS: await pg.locator("#airKindSec").screenshot(path=f"{SHOTS}/floodguard-airtime-{tag}.png")
                if SHOTS: await pg.locator("#ohAdvSec").screenshot(path=f"{SHOTS}/floodguard-advertlimit-{tag}.png")
                # People
                await pg.goto("http://127.0.0.1:18193/#/people"); await pg.wait_for_timeout(1500)
                await pg.click("#pplMoreChips summary"); await pg.wait_for_timeout(200)
                chip=pg.locator("#pplChips button",has_text="Changes name")
                check(await chip.count()==1,f"{tag}: Changes name filter offered")
                await chip.first.click(); await pg.wait_for_timeout(1200)
                names=await pg.eval_on_selector_all("#pplList details summary .what","s=>s.map(x=>x.firstChild.textContent)")
                check(names==["Hilltop Hiker"],f"{tag}: a name whose device changed name (the other name was never heard on a channel): {names}")
                await pg.click("#pplList details summary"); await pg.wait_for_timeout(300)
                body=await pg.inner_text("#pplList")
                check("Also called" in body and "Hilltop Mobile" in body,f"{tag}: Also called shown")
                await scan("People")
                if SHOTS: await pg.locator("#pplSec").screenshot(path=f"{SHOTS}/people-changes-name-{tag}.png")
                await pg.locator("#pplChips button",has_text="Active").first.click(); await pg.wait_for_timeout(1000)
                await pg.fill("#pplFind","Sparky"); await pg.wait_for_timeout(1500)
                check("more than one device" in await pg.inner_text("#pplList"),f"{tag}: a name two devices use is tagged")
                # Messages
                await pg.goto("http://127.0.0.1:18193/#/messages"); await pg.wait_for_timeout(1500)
                allm=pg.locator("#qChips button, .q-chips button",has_text="All")
                if await allm.count(): await allm.first.click(); await pg.wait_for_timeout(1200)
                q=await pg.inner_text("#qList")
                check("Reacted 👍 to Canal Boat Ted" in q,f"{tag}: a reaction reads as one in Messages")
                await scan("Messages")
                if SHOTS: await pg.locator("#qList").screenshot(path=f"{SHOTS}/messages-reaction-{tag}.png")
                # Health
                await pg.goto("http://127.0.0.1:18193/#/health"); await pg.wait_for_timeout(1500)
                await pg.evaluate("document.body.classList.add('advanced')"); await pg.wait_for_timeout(200)
                h=await pg.inner_text("#hStatsAdv")
                check("Rules last sent to openHop" in h and "Evidence log" in h and "Messages you let through this week" in h,f"{tag}: new Health readings")
                await scan("Health")
                if SHOTS: await pg.locator("#hStatsAdv").screenshot(path=f"{SHOTS}/health-readings-{tag}.png")
                check(not errs,f"{tag}: no script errors: {errs[:2]}")
                await ctx.close()
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
