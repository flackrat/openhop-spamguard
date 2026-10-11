import json, asyncio, time
from playwright.async_api import async_playwright
import os
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI=open(os.path.join(REPO,'ui.html')).read()
LF=os.environ.get('LEAFLET_DIST', os.path.join(REPO,'tests','.leaflet','node_modules','leaflet','dist'))+'/'
now=time.time()
def ent(name,lat,lon,d7,exact,blocked=False,codes=("98",)): return {"key":name*8,"name":name,"lat":lat,"lon":lon,"code":codes[0],"d1":d7,"d7":d7,"exact":exact,"codes":list(codes),"last":now,"blocked":blocked,"typical_before":1}
ents=[dict(ent("",51.1,-1.75,20,20),kind="area",near=["Martinsell","Morgans"],claims=["Liar"],spread_km=12,key="area:98:0"),ent("Sure A",51.07,-1.79,12,12,True),ent("Sure B",51.2,-0.2,6,4),ent("Guess C",51.5,0.27,30,0),ent("Guess D",51.3,-0.8,5,1)]
st={"version":"5.13.3","metrics":{"d1":{},"d7":{"m":1,"spam":53},"hourly":[],"daily":[],"by_hour":[],"sources":[{"hop":"98","d7":53,"d1":53,"last":now,"blocked":False,"allowed":False,"candidates":[],"likely":None}],
 "entries":ents,"unplaced":{"d1":2,"d7":2},"me":{"name":"Me","lat":51.46,"lon":-0.97},"radio_known":True,"map_directory":True,"public_repeaters":4000,"public_error":None,"since":now-86400*7}}
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":420,"height":900})
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
    await pg.goto("http://sg.test/#/sources"); await pg.wait_for_timeout(4000)
    async def state():
      return await pg.evaluate("[document.querySelectorAll('#mapBox path.leaflet-interactive').length, document.querySelector('#mapNote').textContent, document.querySelector('#mapGuess').checked]")
    await pg.evaluate("renderSources(S)"); await pg.wait_for_timeout(800)
    s1=await state(); print(s1)
    await pg.screenshot(path=os.path.join(REPO,"tests",".out_guess_off.png"),full_page=False)
    await pg.evaluate("MAPLAYER.eachLayer(l=>{if(l.getPopup&&l.getPopup()&&/Unlisted/.test(l.getPopup().getContent()))l.openPopup()})"); await pg.wait_for_timeout(400)
    print("popup:", await pg.evaluate("(document.querySelector('.leaflet-popup-content')||{}).innerText"))
    await pg.screenshot(path=os.path.join(REPO,"tests",".out_area_popup.png"))
    await pg.click("#mapGuess"); await pg.wait_for_timeout(600); s2=await state(); print(s2)
    await pg.screenshot(path=os.path.join(REPO,"tests",".out_guess_on.png"))
    await pg.reload(); await pg.wait_for_timeout(2000); await pg.evaluate("renderSources(S)"); await pg.wait_for_timeout(800); s3=await state(); print("after reload",s3[0],s3[2]); s3ok=s3[0]==6
    print("errors",errs)
    assert s1[0]==4 and "37 of 75" in s1[1] and s2[0]==6 and s3[2] and s3ok
    print("ok")
asyncio.run(main())
