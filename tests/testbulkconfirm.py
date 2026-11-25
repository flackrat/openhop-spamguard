# Answering several names at once asks for a second press, saying how many messages and names it covers.
# One name's messages are answered straight away. Example data only.
import sys, os, asyncio
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1000,"height":900})
        sent=[]; pg.on("request",lambda r: sent.append(r.url) if r.url.endswith("/verdict") else None)
        await pg.goto("http://127.0.0.1:18171/#/messages"); await pg.wait_for_timeout(2000)
        await pg.click('[data-q="letthrough"]'); await pg.wait_for_timeout(1500)
        await pg.locator(".q-grp").first.click(); await pg.wait_for_timeout(300)
        await pg.click('#qBulk [data-qb="spam"]'); await pg.wait_for_timeout(500)
        w=await pg.locator("#qBulkWarn").text_content() if await pg.locator("#qBulkWarn").count() else ""
        check(not sent,"the first press sends nothing")
        check("6 different names" in w and "again" in w,f"it says how many names and asks again: {w!r}")
        await pg.click('#qBulk [data-qb="spam"]'); await pg.wait_for_timeout(1500)
        check(len(sent)==6,f"the second press answers them all ({len(sent)})")
        # ticking a different set asks again
        sent.clear()
        await pg.click('[data-q="stopped"]'); await pg.wait_for_timeout(1200)
        boxes=pg.locator("#qList [data-qt]")
        if await boxes.count():
            await boxes.first.check(); await pg.wait_for_timeout(200)
            await pg.click('#qBulk [data-qb="spam"]'); await pg.wait_for_timeout(1200)
            check(len(sent)==1,"one name's message is answered at once")
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed"); os._exit(1 if fail else 0)
