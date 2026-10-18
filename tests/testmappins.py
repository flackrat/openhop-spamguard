import json, asyncio, time
from playwright.async_api import async_playwright
import os
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI=open(os.path.join(REPO,'ui.html')).read()
LF=os.environ.get('LEAFLET_DIST', os.path.join(REPO,'tests','.leaflet','node_modules','leaflet','dist'))+'/'
now=time.time()
def ent(name,lat,lon,d7,exact,blocked=False,codes=("98",)): return {"key":name*8,"name":name,"lat":lat,"lon":lon,"code":codes[0],"d1":d7,"d7":d7,"exact":exact,"codes":list(codes),"last":now,"blocked":blocked,"typical_before":1}
# Confidence pins: "Shared" uses a code two other repeaters heard here also use (one with no location),
# "Unique" is the only repeater heard with its code. All names and places made up.
ents=[dict(ent("Shared",51.07,-1.79,12,12,True),kind="id",shared={"others":2,"unlocated":1}),
      dict(ent("Unique",51.2,-0.2,8,8,codes=("4C",)),kind="id",shared={"others":0,"unlocated":0})]
st={"version":"5.13.3","metrics":{"d1":{},"d7":{"m":1,"spam":53},"hourly":[],"daily":[],"by_hour":[],"sources":[{"hop":"98","d7":53,"d1":53,"last":now,"blocked":False,"allowed":False,"candidates":[],"likely":None}],
 "entries":ents,"unplaced":{"d1":2,"d7":2},"me":{"name":"Me","lat":51.78,"lon":0.06},"radio_known":True,"map_directory":True,"public_repeaters":4000,"public_error":None,"since":now-86400*7}}
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
    n_int, note, _ = await state()
    n_all = await pg.evaluate("document.querySelectorAll('#mapBox path').length")
    async def popup(name):
      await pg.evaluate(f"MAPLAYER.eachLayer(l=>{{if(l.getPopup&&l.getPopup()&&l.getPopup().getContent().includes('<b>{name}</b>'))l.openPopup()}})")
      await pg.wait_for_timeout(400)
      return await pg.evaluate("(document.querySelector('.leaflet-popup-content')||{}).innerText")
    p_shared = await popup("Shared")
    await pg.screenshot(path=os.path.join(REPO,"tests",".out_shared_pin.png"))
    p_unique = await popup("Unique")
    labels = await pg.evaluate("[...document.querySelectorAll('#mapBox path.leaflet-interactive')].map(p=>p.getAttribute('aria-label')||'')")
    print(n_int, n_all, note, p_shared, p_unique, labels, errs, sep="\n")
    checks = [
      (n_int == 3, "two pins and your repeater stay clickable"),
      (n_all >= n_int + 2, "a ring is drawn for the shared pin (plus its blocked centre)"),
      ("dotted outer ring" in note, "the note explains the ring"),
      ("also used by 2 other repeaters heard here, 1 with no location" in p_shared, "shared popup says how many"),
      ("No other repeater heard here uses this code." in p_unique, "unique popup says so"),
      (any("code also used by 2 other repeaters" in l for l in labels), "screen readers hear it too"),
      (not errs, "no page errors"),
    ]
    bad = [m for c, m in checks if not c]
    for m in bad: print("FAIL", m)
    print(f"{len(checks)-len(bad)} passed, {len(bad)} failed")
    assert not bad
asyncio.run(main())
