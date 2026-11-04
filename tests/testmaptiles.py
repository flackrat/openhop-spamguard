# Map tiles must reach OpenStreetMap with the page's address as the referrer. The page itself sends no
# referrer anywhere else (web safety), and OpenStreetMap refuses tile requests that carry none. Uses
# SpamGuard's real web server and its real security headers. No real tiles are fetched.
import sys, os, asyncio
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
g.me={"name":"Home Mast","lat":51.5,"lon":-0.5,"hash":"A1"}
LF=os.path.join(os.path.dirname(os.path.abspath(__file__)),".leaflet","node_modules","leaflet","dist")+"/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(viewport={"width":1280,"height":900})).new_page()
        tiles=[]; csp=[]
        pg.on("console",lambda m: csp.append(m.text) if "Content Security Policy" in m.text else None)
        async def route(r):
            u=r.request.url
            if "leaflet.js" in u: return await r.fulfill(path=LF+"leaflet.js",content_type="application/javascript")
            if "leaflet.css" in u: return await r.fulfill(path=LF+"leaflet.css",content_type="text/css")
            if "tile.openstreetmap.org" in u:
                tiles.append((u, (await r.request.all_headers()).get("referer")))
                return await r.fulfill(status=204)
            await r.continue_()
        await pg.route("**/*",route)
        resp=await pg.goto("http://127.0.0.1:18171/#/sources"); await pg.wait_for_timeout(3500)
        check((resp.headers or {}).get("referrer-policy")=="no-referrer","the page still sends no referrer by default")
        check(tiles, f"map tiles were requested ({len(tiles)})")
        check(tiles and all(u.startswith("https://tile.openstreetmap.org/") for u,_ in tiles),"tiles come from OpenStreetMap's single tile host")
        check(tiles and all(ref and ref.startswith("http://127.0.0.1:18171") for _,ref in tiles),"each tile request carries the page's address as referrer: "+str(tiles[:1]))
        check(tiles and all(ref and ref.rstrip("/")=="http://127.0.0.1:18171" for _,ref in tiles),"only the address, never the page path")
        check(not csp,"no tile is blocked by the page's security policy "+str(csp[:1]))
        await b.close()
asyncio.run(main())
print("testmaptiles: %d ok, %d failed"%(ok,fail)); sys.exit(1 if fail else 0)
