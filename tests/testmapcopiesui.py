# 6.45.0: the spam map's confidence circles, its table, and copied names, in a browser with made-up data.
import json, asyncio, time, os, sys
from playwright.async_api import async_playwright
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI=open(os.path.join(REPO,'ui.html')).read()
LF=os.environ.get('LEAFLET_DIST', os.path.join(REPO,'tests','.leaflet','node_modules','leaflet','dist'))+'/'
AXE=open(os.environ.get("AXE_JS", os.path.join(REPO,"tests",".axe","node_modules","axe-core","axe.min.js"))).read()
now=time.time(); ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def ent(name,lat,lon,d7,level,kind,radius,code):
    return {"key":name or "area:"+code,"name":name,"lat":lat,"lon":lon,"code":code,"d1":1,"d7":d7,"exact":d7 if level=="certain" else 0,"codes":[code],"last":now,"blocked":False,"typical_before":0,"kind":kind,"level":level,"radius_km":radius,"near":["Plain Relay"] if kind=="area" else [],"claims":[],"s7":3,"s1":1,"shared":{"others":0,"unlocated":0}}
ents=[ent("Hill Fort",40.27,-96.16,120,"certain","id",48,"5D"),ent("",39.1,-96.8,80,"likely","area",34,"EC"),ent("Vale Rpt",39.5,-97.5,30,"guess","guess",30,"29")]
copies=[{"name":"Moor Walker","n":10,"last":now,"held":True,"at":[{"lat":40.25,"lon":-96.0,"name":"Hill Fort","code":"5D","kind":"id","sure":True,"n":8,"last":now},{"lat":38.9,"lon":-95.5,"name":"Far Rpt","code":"82","kind":"guess","sure":False,"n":2,"last":now}],"real":{"lat":40.6,"lon":-93.3,"name":"Coast Rpt","kind":"id","sure":True}}]
st={"version":"6.45.0","metrics":{"d1":{},"d7":{"m":1,"spam":230},"hourly":[],"daily":[],"by_hour":[],"sources":[{"hop":"5D","d7":120,"d1":40,"last":now,"blocked":False,"allowed":False,"candidates":[],"likely":None}],
 "entries":ents,"unplaced":{"d1":0,"d7":0},"copies":copies,"senders":[],"me":{"name":"Me","lat":40.2,"lon":-95.5},"radio_known":True,"map_directory":True,"public_repeaters":4000,"public_error":None,"since":now-86400*7}}
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    for scheme,vw in (("light",1100),("dark",1100),("light",360)):
      pg=await (await b.new_context(viewport={"width":vw,"height":1200},color_scheme=scheme)).new_page()
      errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
      async def h(route):
        u=route.request.url
        if u.endswith("/status"): return await route.fulfill(json=st)
        if "leaflet.js" in u: return await route.fulfill(path=LF+"leaflet.js",content_type="application/javascript")
        if "leaflet.css" in u: return await route.fulfill(path=LF+"leaflet.css",content_type="text/css")
        if "tile.openstreetmap" in u: return await route.fulfill(status=204)
        if u.startswith("http://sg.test/"): return await route.fulfill(body=UI,content_type="text/html")
        await route.fulfill(json={})
      await pg.route("**/*",h)
      await pg.goto("http://sg.test/#/sources"); await pg.wait_for_timeout(3000)
      await pg.evaluate("renderSources(S)"); await pg.wait_for_timeout(700)
      circles=await pg.evaluate("(()=>{let n=0;MAPLAYER.eachLayer(l=>{if(l instanceof L.Circle)n++});return n})()")
      check(circles==2,f"an area circle for each confident place, guesses hidden ({circles})")
      t=await pg.inner_text("#entTable")
      check("Hill Fort" in t and "Certain" in t and "48 km" in t and "Likely" in t and "Plain Relay" in t and "Vale Rpt" not in t,"the table says where, how sure and how far")
      sq=await pg.evaluate("document.querySelectorAll('#mapBox .map-sq').length")
      check(sq==2,f"a square for the copies and one for the real person; the rough guess hidden ({sq})")
      cl=await pg.inner_text("#copyList")
      check("Moor Walker" in cl and "10 copies" in cl and "Far Rpt (rough guess)" in cl and "Coast Rpt" in cl,"copied names are listed in words")
      lab=await pg.evaluate("[...document.querySelectorAll('#mapBox [aria-label]')].map(e=>e.getAttribute('aria-label')).join(' | ')")
      check("Copies of Moor Walker came from here" in lab and "sender within about 48 km" in lab,"screen readers hear the copies and the area")
      await pg.evaluate("MAPLAYER.eachLayer(l=>{if(l.getPopup&&l.getPopup()&&l.getPopup().getContent().includes('Copies of Moor Walker'))l.openPopup()})"); await pg.wait_for_timeout(300)
      pop=await pg.evaluate("(document.querySelector('.leaflet-popup-content')||{}).innerText||''")
      check("8 probable copies" in pop and "real Moor Walker is usually heard from Coast Rpt" in pop,"the copies' popup explains")
      await pg.click("#mapCopies"); await pg.wait_for_timeout(500)
      check(await pg.evaluate("document.querySelectorAll('#mapBox .map-sq').length")==0,"copied names can be hidden")
      await pg.click("#mapCopies"); await pg.click("#mapGuess"); await pg.wait_for_timeout(500)
      check(await pg.evaluate("document.querySelectorAll('#mapBox .map-sq').length")==3,"best guesses show the guessed copies too")
      await pg.click("#mapGuess"); await pg.wait_for_timeout(300)
      mp=await pg.evaluate("""(()=>{const e=(k,lat,lon,d7,lv)=>({key:k,name:k,lat,lon,d7,d1:1,exact:lv==='certain'?d7:0,s7:2,code:k,codes:[k],level:lv,radius_km:30,kind:'id'});
        const r=mergePlaces([e('A',40.0,-96.0,50,'certain'),e('B',40.05,-96.02,40,'likely'),e('C',39.0,-94.5,10,'certain')]);
        return [r.length,r[0].d7,r[0].codes.join(','),r[0].level,r[0].s7,r[0].radius_km>30]})()""")
      check(mp==[2,90,"A,B","likely",2,True],f"places a few km apart become one, never surer than a big part of it ({mp})")
      await pg.add_script_tag(content=AXE)
      v=await pg.evaluate("""async()=>(await axe.run(document.querySelector('[data-page=sources]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
      check(not v,f"no WCAG 2.1 AA problems ({scheme} {vw}): {v}")
      check(await pg.evaluate("document.documentElement.scrollWidth")<=vw+1,"no sideways scroll")
      check(not errs,f"no script errors {errs}")
    await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
