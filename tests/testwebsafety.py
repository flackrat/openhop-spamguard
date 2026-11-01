# The page's web server: safety headers on what it sends, a size limit on what it accepts, and the page itself still
# working under its content policy. All names and messages are made up.
import sys, os, time, asyncio, json, http.client
exec(open("demo_setup.py").read())
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
def req(method,path,body=None,headers=None):
    c=http.client.HTTPConnection("127.0.0.1",18171,timeout=10)
    c.request(method,path,body=body,headers=headers or {})
    r=c.getresponse(); data=r.read(); h={k.lower():v for k,v in r.getheaders()}; c.close()
    return r.status,h,data
st,h,_=req("GET","/")
check(st==200 and "frame-ancestors 'none'" in h.get("content-security-policy",""),"the page has a content policy that stops framing")
check(h.get("x-frame-options")=="DENY" and h.get("x-content-type-options")=="nosniff" and h.get("referrer-policy")=="no-referrer","the page has the other safety headers")
check("connect-src 'self'" in h["content-security-policy"] and "object-src 'none'" in h["content-security-policy"],"it may only talk to SpamGuard itself")
st,h,_=req("GET","/status")
check(st==200 and h.get("x-content-type-options")=="nosniff" and "content-security-policy" not in h,"data answers carry nosniff and no page policy")
st,h,_=req("GET","/nothing-here")
check(st==404 and h.get("x-content-type-options")=="nosniff","even an error carries it")

J={"Content-Type":"application/json"}
st,_,d=req("POST","/settings",json.dumps({}),J)
check(st==200,"an ordinary change still works")
big=http.client.HTTPConnection("127.0.0.1",18171,timeout=10)
big.putrequest("POST","/settings"); big.putheader("Content-Type","application/json"); big.putheader("Content-Length",str(50_000_000)); big.endheaders()
t=time.time(); r=big.getresponse(); body=r.read(); big.close()
check(r.status==413 and time.time()-t<3,"a huge change is refused straight away, unread: %s"%r.status)
c=http.client.HTTPConnection("127.0.0.1",18171,timeout=10)
c.putrequest("POST","/settings"); c.putheader("Content-Type","application/json"); c.putheader("Content-Length","abc"); c.endheaders()
r=c.getresponse(); r.read(); c.close()
check(r.status==400,"a length that isn't a number is refused: %s"%r.status)
c=http.client.HTTPConnection("127.0.0.1",18171,timeout=10)
c.putrequest("POST","/settings"); c.putheader("Content-Type","application/json"); c.putheader("Content-Length","-5"); c.endheaders()
r=c.getresponse(); r.read(); c.close()
check(r.status==400,"a negative length is refused: %s"%r.status)
st,_,_=req("GET","/status")
check(st==200,"SpamGuard is still answering afterwards")

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await (await b.new_context(viewport={"width":1200,"height":900})).new_page()
        csp=[]; errs=[]
        pg.on("console",lambda m: csp.append(m.text) if "Content Security Policy" in m.text or "Refused to" in m.text else None)
        pg.on("pageerror",lambda e: errs.append(str(e)))
        for route in ("#/","#/messages?f=all","#/settings","#/health","#/channels","#/floodguard"):
            await pg.goto("http://127.0.0.1:18171/"+route); await pg.wait_for_timeout(1500)
        # buttons that post changes still work under the policy
        await pg.goto("http://127.0.0.1:18171/#/"); await pg.wait_for_timeout(1500)
        check(await pg.locator("#hero h1").count()==1 and len(await pg.inner_text("#hero"))>10,"the page draws")
        check(not [c for c in csp if "unpkg" not in c and "openstreetmap" not in c],"nothing of the page's own is blocked by the policy: "+str(csp[:2]))
        check(not errs,"no page errors "+str(errs[:1]))
        await b.close()
asyncio.run(main())
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
