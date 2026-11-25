# Text size: two smaller sizes as well as the larger ones. Smaller text still fits a phone without sideways
# scrolling, buttons stay big enough to tap, and the choice is remembered.
import sys, os, asyncio
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":360,"height":800})
        errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:18171/#/display"); await pg.wait_for_timeout(1200)
        vals=[await x.get_attribute("data-v") for x in await pg.query_selector_all("[data-opt=text] button")]
        check(vals==["smaller","small","normal","large","larger"],f"five sizes, smallest first: {vals}")
        for v,px in (("smaller",14),("small",15),("normal",16)):
            await pg.click(f"[data-opt=text] button[data-v={v}]"); await pg.wait_for_timeout(200)
            fs=await pg.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
            check(abs(fs-px)<0.1,f"{v}: text is {px}px ({fs})")
        await pg.click("[data-opt=text] button[data-v=smaller]")
        await pg.reload(); await pg.wait_for_timeout(1200)
        check(await pg.evaluate("document.documentElement.dataset.text")=="smaller","remembered after reload")
        for page in ("overview","floodguard","people","blocks","settings"):
            await pg.evaluate(f"location.hash='#/{page}'"); await pg.wait_for_timeout(700)
            w=await pg.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
            check(w<=1,f"{page}: no sideways scrolling with smaller text ({w}px)")
        await pg.evaluate("location.hash='#/overview'"); await pg.wait_for_timeout(600)
        small=await pg.evaluate("""[...document.querySelectorAll('.seg button,button.primary')].filter(b=>b.offsetParent).map(b=>b.getBoundingClientRect().height).filter(h=>h<44).length""")
        check(small==0,f"buttons stay at least 44px tall ({small} smaller)")
        check(not errs,f"no page errors {errs}")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); os._exit(1 if fail else 0)
