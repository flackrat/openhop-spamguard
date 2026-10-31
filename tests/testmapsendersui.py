# The spam map in the browser: a repeat spammer drawn as one purple area with lines to the repeaters that hear
# them first, circles sized by messages or senders, a key that is always shown, and "Show these messages"
# opening the message list filtered to that point. All names, places and messages are made up.
import json, asyncio, time, os
from playwright.async_api import async_playwright
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI=open(os.path.join(REPO,'ui.html')).read()
LF=os.environ.get('LEAFLET_DIST', os.path.join(REPO,'tests','.leaflet','node_modules','leaflet','dist'))+'/'
now=time.time()
ents=[{"key":"C4"*4,"name":"Ridge Relay","lat":51.50,"lon":-0.90,"code":"C4","d1":30,"d7":40,"s7":2,"s1":2,"exact":40,"codes":["C4"],"last":now,
       "blocked":False,"typical_before":0,"kind":"id","shared":{"others":0,"unlocated":0}},
      {"key":"9D"*4,"name":"Canal Node","lat":51.30,"lon":-1.10,"code":"9D","d1":4,"d7":6,"s7":6,"s1":4,"exact":6,"codes":["9D"],"last":now,
       "blocked":True,"typical_before":0,"kind":"id","shared":{"others":0,"unlocated":0}}]
snd=[{"key":"sender:abc","names":["Fox One","Fox Two"],"lat":51.51,"lon":-0.85,"radius_km":6.5,"d7":17,"d1":5,"spread":False,
      "repeaters":[{"name":"Ridge Relay","code":"C4","n":8,"lat":51.50,"lon":-0.90},{"name":"Mill Hill Rpt","code":"E1","n":5,"lat":51.56,"lon":-0.82},
                   {"name":"Canal Node","code":"7B","n":4,"lat":51.46,"lon":-0.80}]}]
st={"version":"6.10.0","mode":"protect","metrics":{"d1":{},"d7":{"m":1,"spam":46},"hourly":[],"daily":[],"by_hour":[],
 "sources":[{"hop":"C4","d7":40,"d1":30,"last":now,"blocked":False,"allowed":False,"candidates":[],"likely":None}],
 "entries":ents,"unplaced":{"d1":0,"d7":3},"senders":snd,"senders_unplaced":1,"me":{"name":"Me","lat":51.46,"lon":-0.97},
 "radio_known":True,"map_directory":True,"public_repeaters":4000,"public_error":None,"since":now-86400*7}}
asked=[]
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1100,"height":1000})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    async def h(route):
      u=route.request.url
      if u.endswith("/status"): return await route.fulfill(json=st)
      if u.endswith("/quarantine"):
        asked.append(json.loads(route.request.post_data or "{}"))
        return await route.fulfill(json={"source":"evidence","days":7,"counts":{"stopped":1,"held":0,"letthrough":0,"genuine":0},"total":1,"shown":1,"mode":"protect",
          "rows":[{"ts":now-60,"sender":"UD6DWREK","text":"FREE PRIZE claim now","channel":"Public","path":"C4>9D","status":"stopped","why":"A copy of a message already sent under another name",
                   "copies":1,"senders":1,"known":False,"spammer":False,"label":None,"matched":"text:1","packet":"p1"}]})
      if "leaflet.js" in u: return await route.fulfill(path=LF+"leaflet.js",content_type="application/javascript")
      if "leaflet.css" in u: return await route.fulfill(path=LF+"leaflet.css",content_type="text/css")
      if "tile.openstreetmap" in u: return await route.fulfill(status=204)
      if u.startswith("http://sg.test/"): return await route.fulfill(body=UI,content_type="text/html")
      await route.fulfill(json={})
    await pg.route("**/*",h)
    await pg.goto("http://sg.test/#/sources"); await pg.wait_for_timeout(3000)
    await pg.evaluate("renderSources(S)"); await pg.wait_for_timeout(800)
    await pg.screenshot(path=os.path.join(REPO,"tests",".out_map_senders.png"))
    key=await pg.text_content("#mapKey"); note=await pg.text_content("#mapNote")
    async def popup(txt):
      await pg.evaluate(f"MAPLAYER.eachLayer(l=>{{if(l.getPopup&&l.getPopup()&&l.getPopup().getContent().includes({json.dumps(txt)}))l.openPopup()}})")
      await pg.wait_for_timeout(400)
      return await pg.evaluate("(document.querySelector('.leaflet-popup-content')||{}).innerText||''")
    ps=await popup("One sender")
    lines=await pg.evaluate("(()=>{let n=0;MAPLAYER.eachLayer(l=>{if(l instanceof L.Polyline&&!(l instanceof L.Polygon))n++});return n})()")
    radius_msgs=await pg.evaluate("(()=>{let r=0;MAPLAYER.eachLayer(l=>{if(l.getPopup&&l.getPopup()&&l.getPopup().getContent().includes('<b>Ridge Relay</b>'))r=l.getRadius()});return r})()")
    await pg.click("#mapBy [data-v=senders]"); await pg.wait_for_timeout(600)
    radius_snd=await pg.evaluate("(()=>{let r=0;MAPLAYER.eachLayer(l=>{if(l.getPopup&&l.getPopup()&&l.getPopup().getContent().includes('<b>Ridge Relay</b>'))r=l.getRadius()});return r})()")
    key2=await pg.text_content("#mapKey")
    pr=await popup("<b>Ridge Relay</b>")
    await pg.click(".leaflet-popup-content [data-msgs]"); await pg.wait_for_timeout(1200)
    hashv=await pg.evaluate("location.hash"); filt=await pg.text_content("#qFilters"); first=await pg.text_content("#qList")
    await pg.uncheck("#mapSenders") if False else None
    checks=[
      ("One repeat spammer" in key and "Your repeater" in key and "Best guess" in key, "the map key is always shown"),
      ("Fox One, Fox Two" in ps and "Heard first by 3 repeaters" in ps and "6.5 km" in ps, "the purple area says it is one sender heard by three repeaters: "+ps[:120]),
      ("17 messages in 7 days" in ps and "not only the copies held" in ps, "and that every message they sent counts"),
      (lines==3, f"lines join the area to each of the three repeaters: {lines}"),
      (radius_snd<radius_msgs, f"sizing by senders shrinks the busy circle sent by only 2 names: {radius_msgs} -> {radius_snd}"),
      ("number of senders" in key2, "the key says what the size means"),
      ("from 2 senders" in pr, "a circle's popup says how many senders"),
      (hashv.startswith("#/messages") and "Ridge Relay" in filt, f"Show these messages opens the message list filtered to that place: {hashv} {filt}"),
      (asked and asked[-1].get("codes")==["C4"] and asked[-1].get("days")==7, f"asking for that repeater's code over 7 days: {asked[-1] if asked else None}"),
      ("UD6DWREK" in first, "and lists what came through there"),
      ("1 more not placed yet" in note, "repeat spammers that can't be placed are counted"),
      (not errs, f"no page errors: {errs}"),
    ]
    bad=[m for c,m in checks if not c]
    for m in bad: print("FAIL",m)
    print(f"{len(checks)-len(bad)} passed, {len(bad)} failed")
    await b.close()
    assert not bad
asyncio.run(main())
