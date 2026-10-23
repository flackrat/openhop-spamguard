# Accessibility checks for SpamGuard's page (WCAG 2.1 AA): an axe-core scan of every page in light and
# dark, desktop and phone sizes, plus hands-on checks of keyboard use, the phone menu, the display options,
# chart tables and the map. All data is made up. Needs Playwright with Chromium and the axe-core npm package.
import sys, os, json, asyncio, urllib.request
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(REPO,"tests")); os.chdir(os.path.join(REPO,"tests"))
exec(open("demo_setup.py").read())
from playwright.async_api import async_playwright
AXE=open(os.environ.get("AXE_JS", os.path.join(REPO,"tests",".axe","node_modules","axe-core","axe.min.js"))).read()
LF=REPO+"/tests/.leaflet/node_modules/leaflet/dist/"
now=time.time()
ME=(52.93,-0.62)   # made-up spot for "your repeater"
def k(code): return code+"".join("%02X"%((i*37+ord(code[0])*11)%256) for i in range(31))
def rep(code,name,lat,lon): return {"key":k(code),"name":name,"seen":now-3600,"lat":lat,"lon":lon}
entries=[
 {"key":"area:C4:0","name":"","lat":52.06,"lon":-2.62,"code":"C4","d1":19,"d7":46,"exact":46,"codes":["C4"],"last":now-900,"kind":"area",
  "near":["Quarry Hill Solar","Beacon Lane Rpt","Old Mill Mast"],"claims":["FREE WIFI NODE"],"spread_km":14,"blocked":True,"typical_before":0},
 {"key":k("5E"),"name":"Canal Basin Rpt","lat":52.38,"lon":-0.55,"code":"5E","d1":6,"d7":18,"exact":18,"codes":["5E"],"last":now-5400,"kind":"id",
  "near":[],"claims":[],"spread_km":None,"blocked":False,"typical_before":0},
 {"key":"area:C4:1","name":"","lat":51.62,"lon":-3.05,"code":"C4","d1":2,"d7":9,"exact":9,"codes":["C4"],"last":now-20000,"kind":"area",
  "near":["Hawthorn Ridge","Market Cross Node"],"claims":[],"spread_km":19,"blocked":True,"typical_before":0},
 {"key":k("B7"),"name":"Lakeside Solar","lat":52.62,"lon":-0.48,"code":"B7","d1":1,"d7":5,"exact":0,"codes":["B7"],"last":now-40000,"kind":"guess",
  "near":[],"claims":[],"spread_km":None,"blocked":False,"typical_before":2},
]
sources=[
 {"hop":"C4","d7":55,"d1":21,"last":now-900,"blocked":True,"allowed":False,"candidates":[rep("C4","Ridgeway Relay",51.55,-1.40)],"likely":{"name":"Quarry Hill Solar","key":"area:C4:0","exact":False}},
 {"hop":"5E","d7":18,"d1":6,"last":now-5400,"blocked":False,"allowed":False,"candidates":[rep("5E","Canal Basin Rpt",52.38,-0.55)],"likely":{"name":"Canal Basin Rpt","key":k("5E"),"exact":True}},
 {"hop":"B7","d7":5,"d1":1,"last":now-40000,"blocked":False,"allowed":False,"candidates":[rep("B7","Lakeside Solar",52.62,-0.48),rep("B7","Moorgate Tower",53.4,-1.5)],"likely":None},
]
def patch(d):
    d["summary"]["caught_24h"]=d["metrics"]["d1"]["c"]
    d["rule_summary"]={"after_yours":True,"yours":1,"rules":[[9001,"spamguard:text:ab12 (duplicate) text \"example\"","drop","Blocks a packet that is a channel message, is on a channel SpamGuard reads, contains the text \"example\""],
                                                         [9002,"spamguard:known-people","allow","Lets through a packet that is from someone SpamGuard knows"]]}
    m=d["metrics"]; m["since"]=now-8*86400
    m.update({"me":{"name":"Example Repeater","hash":"5A","lat":ME[0],"lon":ME[1]},"entries":entries,"sources":sources,
              "unplaced":{"d1":0,"d7":3},"learned":2410,"advert_routes":7320,"map_working":False,
              "map_directory":True,"public_repeaters":4380,"public_error":None})
    return d
LF=os.path.join(REPO,'tests','.leaflet','node_modules','leaflet','dist')+'/'

R=[]
def check(n,c,d=""): R.append((n,bool(c))); print(("PASS " if c else "FAIL ")+n+("" if c else f"  -- {d}"))
async def setup(ctx):
    pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda x:errs.append(str(x)))
    async def fix(route):
        u=route.request.url
        if "/status" in u:
            import urllib.request
            d=json.loads(urllib.request.urlopen("http://127.0.0.1:18171/status").read())
            return await route.fulfill(status=200,content_type="application/json",body=json.dumps(patch(d)))
        if "leaflet.js" in u: return await route.fulfill(path=LF+"leaflet.js",content_type="application/javascript")
        if "leaflet.css" in u: return await route.fulfill(path=LF+"leaflet.css",content_type="text/css")
        if "tile.openstreetmap" in u: return await route.fulfill(status=204)
        return await route.continue_()
    await pg.route("**/*",fix); return pg,errs
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    # desktop keyboard
    ctx=await b.new_context(viewport={"width":1280,"height":900}); pg,errs=await setup(ctx)
    await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(1500)
    await pg.keyboard.press("Tab"); f=await pg.evaluate("document.activeElement.id")
    check("first Tab reaches 'Skip to content'", f=="skipLink", f)
    vis=await pg.evaluate("document.activeElement.getBoundingClientRect().left>=0")
    check("skip link visible when focused", vis)
    await pg.keyboard.press("Enter"); f=await pg.evaluate("document.activeElement.tagName+':'+document.activeElement.textContent.slice(0,30)")
    check("skip link moves focus to the page heading", f.startswith("H"), f)
    await pg.focus('#footRules'); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(300)
    st=await pg.evaluate("[document.getElementById('rulesDlg').open, document.querySelectorAll('#rulesList li').length, document.getElementById('rulesList').textContent.includes('channel message')]")
    check("the rules line opens a list of what each rule says", st==[True,2,True], st)
    await pg.add_script_tag(content=AXE)
    v=await pg.evaluate("""async()=>(await axe.run(document.getElementById('rulesDlg'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id)""")
    check("the open rules list has no WCAG 2.1 AA problems", not v, v)
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
    st=await pg.evaluate("[document.getElementById('rulesDlg').open, document.activeElement.id]")
    check("Escape closes the rules list and returns focus to the line", st==[False,"footRules"], st)
    await pg.click('a[data-nav="sources"]'); await pg.wait_for_timeout(1500)
    f=await pg.evaluate("document.activeElement.tagName+':'+document.activeElement.textContent.slice(0,30)")
    check("changing page moves focus to its heading", f.startswith("H2:Spam sources"), f)
    n=await pg.evaluate("document.querySelectorAll('#mapBox path[tabindex=\"0\"][role=button]').length")
    check("map circles reachable by keyboard", n>=4, n)
    lab=await pg.evaluate("[...document.querySelectorAll('#mapBox path[role=button]')].map(e=>e.getAttribute('aria-label'))")
    check("map circles have spoken labels", all(lab) and any("blocked" in x for x in lab), lab)
    await pg.focus('#mapBox path[role=button]'); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(300)
    check("Enter on a map circle opens its popup", await pg.evaluate("!!document.querySelector('.leaflet-popup-content')"))
    dots=await pg.evaluate("[...document.querySelectorAll('#mapBox path')].filter(e=>e.getAttribute('fill')==='#fff').length")
    check("blocked circles get a white centre", dots>=1, dots)
    await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(1500)
    t=await pg.evaluate("[...document.querySelectorAll('details.chart-data')].map(d=>d.querySelectorAll('tr').length)")
    check("each chart has a table of numbers", len(t)==3 and all(x>2 for x in t), t)
    al=await pg.evaluate("['chart24','chart7','chartHour'].map(i=>document.getElementById(i).getAttribute('aria-label'))")
    check("each chart has a description", all(al), al)
    # options
    await pg.goto("http://127.0.0.1:18171/#/display"); await pg.wait_for_timeout(1200)
    fs0=await pg.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
    await pg.click('[data-opt=text] button[data-v=larger]'); await pg.click('[data-opt=contrast] button[data-v=high]'); await pg.click('[data-opt=theme] button[data-v=dark]'); await pg.click('[data-opt=motion] button[data-v=reduce]')
    fs1=await pg.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
    check("Larger text scales the page text", fs1>=fs0*1.2, (fs0,fs1))
    await pg.reload(); await pg.wait_for_timeout(1200)
    st=await pg.evaluate("[document.documentElement.dataset.text,document.documentElement.dataset.theme,document.documentElement.dataset.contrast,document.documentElement.dataset.motion]")
    check("options remembered after reload", st==["larger","dark","high","reduce"], st)
    pr=await pg.evaluate("[...document.querySelectorAll('[data-opt] button[aria-pressed=true]')].map(b=>b.dataset.v)")
    check("chosen options announced as pressed", pr==["larger","dark","high","reduce"], pr)
    bg=await pg.evaluate("getComputedStyle(document.body).backgroundColor")
    check("forced dark theme applies", bg in ("rgb(11, 17, 23)",), bg)
    await ctx.close()
    # phone: drawer and reflow at 320px with larger text
    ctx=await b.new_context(viewport={"width":320,"height":700},is_mobile=True,has_touch=True); pg,errs2=await setup(ctx)
    await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.evaluate("localStorage.setItem('sgtext','larger')"); await pg.reload(); await pg.wait_for_timeout(1500)
    for page in ("overview","sources","blocks","display","settings"):
        await pg.goto(f"http://127.0.0.1:18171/#/{page}"); await pg.wait_for_timeout(700)
        w=await pg.evaluate("document.documentElement.scrollWidth")
        check(f"no sideways scrolling at 320px, larger text ({page})", w<=322, w)
    await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.wait_for_timeout(800)
    hidden=await pg.evaluate("getComputedStyle(document.getElementById('side')).visibility")
    check("closed phone menu is hidden from keyboard and screen readers", hidden=="hidden", hidden)
    await pg.click("#menuBtn"); await pg.wait_for_timeout(400)
    f=await pg.evaluate("[document.activeElement.closest('#side')!=null, document.getElementById('menuBtn').getAttribute('aria-expanded'), document.getElementById('menuBtn').getAttribute('aria-label')]")
    check("opening the menu moves focus into it", f[0] and f[1]=="true" and f[2]=="Close menu", f)
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
    f=await pg.evaluate("[document.activeElement.id, document.body.classList.contains('menu-open')]")
    check("Escape closes the menu and returns focus to the button", f==["menuBtn",False], f)
    sw=await pg.evaluate("[...document.querySelectorAll('label.switch')].filter(l=>l.offsetParent).map(l=>Math.round(l.getBoundingClientRect().height))")
    check("toggle rows are at least 44px tall on phones", all(h>=44 for h in sw), sw)
    await pg.goto("http://127.0.0.1:18171/#/display"); await pg.wait_for_timeout(600); pass
    check("no script errors", not errs and not errs2, errs+errs2)
    # automated scan, every page, both themes, desktop and phone
    PAGES=["overview","blocks","held","lockdown","floodguard","channels","channels","messages","sources","health","updates","help","settings","evidence","display","exceptions","campaigns","activity"]
    for scheme in ("light","dark"):
      for vw,vh,mob in ((1280,900,False),(390,844,True)):
        ctx=await b.new_context(viewport={"width":vw,"height":vh},color_scheme=scheme,is_mobile=mob,has_touch=mob); pg,_=await setup(ctx)
        await pg.goto("http://127.0.0.1:18171/#/overview"); await pg.evaluate("localStorage.setItem('sgadv','1')")
        found=[]
        for page in PAGES:
          await pg.goto(f"http://127.0.0.1:18171/#/{page}"); await pg.reload(); await pg.wait_for_timeout(700)
          await pg.add_script_tag(content=AXE)
          v=await pg.evaluate("""async()=>(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id+':'+v.nodes.length)""")
          found+= [page+"/"+x for x in v]
        check(f"axe finds no WCAG 2.1 AA problems ({scheme}, {'phone' if mob else 'desktop'})", not found, found[:6])
        await ctx.close()
    print(f"{sum(1 for r in R if r[1])}/{len(R)} passed")
asyncio.run(main())
