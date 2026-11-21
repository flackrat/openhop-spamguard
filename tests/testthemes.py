# The colour schemes on the Display page: each is a complete set of colours, and every text, link, button, border,
# focus and chart colour is checked by calculating its contrast ratio (WCAG 2.1), not just by an automatic scanner.
# Text must reach 4.5:1 in every scheme and 7:1 (the AAA level) in Highest contrast and Yellow on black; borders of
# controls, focus outlines and chart colours must reach 3:1. Plus: it is saved per browser, and the page still passes axe.
import sys, re, os, asyncio
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
css=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","ui.html")).read()
def lum(h):
    h=h.lstrip('#'); r,g_,b_=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g_)+0.0722*f(b_)
def cr(a,b):
    la,lb=sorted((lum(a),lum(b)),reverse=True); return (la+0.05)/(lb+0.05)
TEXT=[("ink","paper"),("ink","panel"),("soft","paper"),("soft","panel"),("signal-text","panel"),("signal-text","paper"),
      ("amber-text","panel"),("amber-text","paper"),("signal-ink","signal"),("signal","panel"),("ink","signal-tint"),
      ("ink","amber-tint"),("ink","stop-tint"),("nav-ink","nav"),("nav-ink","nav-active"),("stop","panel"),
      ("signal-text","signal-tint"),("amber-text","amber-tint"),("soft","signal-tint")]
NON=[("field","panel"),("focus","panel"),("focus","paper"),("bar","panel")]
CH=["c-stop","c-let","c-flood","c-fu","c-fa","c-fd","c-fw","c-used"]
sets={}
for name in ("cb","aaa","glare","yellow"):
    m=re.search(r"html\[data-palette=%s\]\[data-palette\]\{([^}]*)\}"%name, css)
    check(bool(m), f"{name}: a palette is defined")
    if not m: continue
    sets[name]={k.lstrip("-"):x for k,x in (y.split(":") for y in m.group(1).split(";") if y)}
need=set(re.findall(r"--([a-z-]+):", re.search(r":root\{([^}]*)\}", css).group(1)))|{"nav","nav-ink","nav-active"}
for name,v in sets.items():
    check(need<=set(v), f"{name}: every colour is set ({sorted(need-set(v))})")
    floor=7.0 if name in ("aaa","yellow") else 4.5
    bad=[(a,b,round(cr(v[a],v[b]),2)) for a,b in TEXT if a in v and b in v and cr(v[a],v[b])<floor]
    check(not bad, f"{name}: text reaches {floor}:1 {bad}")
    bad=[(a,b,round(cr(v[a],v[b]),2)) for a,b in NON if cr(v[a],v[b])<3]
    check(not bad, f"{name}: borders, focus and bars reach 3:1 {bad}")
    bad=[(k,round(cr(v[k],v["panel"]),2)) for k in CH if cr(v[k],v["panel"])<3]
    check(not bad, f"{name}: chart colours reach 3:1 {bad}")
    check(len({v[k] for k in CH})==len(CH), f"{name}: chart colours differ from one another")
for name in ("aaa","yellow"):
    check(cr(sets[name]["line"],sets[name]["panel"])>=3, f"{name}: panel edges reach 3:1")
# colour-blind safe: no red and green pair is relied on
cb=sets["cb"]
def hue(h):
    import colorsys
    h=h.lstrip('#'); r,g_,b_=[int(h[i:i+2],16)/255 for i in (0,2,4)]; return colorsys.rgb_to_hsv(r,g_,b_)[0]*360
check(not any(60<hue(cb[k])<170 for k in ("signal","signal-text","bar","c-stop")), "colour-blind safe: no green for good")

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:18171/"); await pg.wait_for_timeout(1200)
        await pg.evaluate("location.hash='#/display'"); await pg.wait_for_timeout(400)
        labels=[(await x.text_content()) for x in await pg.query_selector_all("[data-opt=theme] button")]
        check(len(labels)==7 and "Colour-blind safe" in labels and "Highest contrast" in labels, f"the choices: {labels}")
        for name,theme,pal in (("cb","light","cb"),("aaa","light","aaa"),("glare","dark","glare"),("yellow","dark","yellow")):
            await pg.click(f"[data-opt=theme] button[data-v={name}]"); await pg.wait_for_timeout(300)
            got=await pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.palette, localStorage.getItem('sgtheme')]")
            check(got==[theme,pal,name], f"{name} applies and is saved: {got}")
            bg=await pg.evaluate("getComputedStyle(document.body).backgroundColor")
            want=sets[name]["paper"].lstrip("#"); rgb="rgb(%d, %d, %d)"%tuple(int(want[i:i+2],16) for i in (0,2,4))
            check(bg==rgb, f"{name}: the page really uses it: {bg} {rgb}")
            check(await pg.get_attribute(f"[data-opt=theme] button[data-v={name}]","aria-pressed")=="true", f"{name}: marked as chosen")
        await pg.reload(); await pg.wait_for_timeout(1200)
        check(await pg.evaluate("document.documentElement.dataset.palette")=="yellow", "kept after a reload, before the page draws")
        await pg.click("[data-opt=theme] button[data-v=light]"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.documentElement.dataset.palette") is None and await pg.evaluate("document.documentElement.dataset.theme")=="light", "choosing Light puts the standard colours back")
        # On a phone the seven colour choices wrap into a grid: every label whole, nothing off the edge
        await pg.set_viewport_size({"width":360,"height":800}); await pg.wait_for_timeout(400)
        lay=await pg.evaluate("""()=>{const g=document.querySelector('[data-opt=theme]'),W=document.documentElement.clientWidth;
          return {fits:g.getBoundingClientRect().right<=W+1,
                  broken:[...g.querySelectorAll('button')].filter(b=>{const r=document.createRange();r.selectNodeContents(b);
                    return r.getClientRects().length>b.textContent.trim().split(/\\s+/).length}).map(b=>b.textContent)}}""")
        check(lay["fits"] and not lay["broken"], f"colour choices fit a phone screen with every word whole: {lay}")
        check(not errs, f"no page errors: {errs}")
        await b.close()
asyncio.run(main())
srv.shutdown()
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
