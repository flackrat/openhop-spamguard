# Floods of made-up names sending random characters. All messages here are made up or generated.
import sys, logging, random, time
from harness import *
logging.disable(logging.WARNING)
ok=fail=0
def check(c,msg):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print("FAIL",msg)
random.seed(11)
GOOD=["Goedemorgen allemaal, mooi weer vandaag in Utrecht!","Weet iemand of de repeater bij Amersfoort weer werkt?",
 "Guten Morgen 👋 alles klar bei euch?","Dzień dobry, czy ktoś mnie słyszy z Krakowa?","Привіт усім! Як справи?",
 "Καλημέρα σε όλους από Αθήνα","こんにちは、テスト送信です","今日は東京でメッシュのテストをしています。","我们正在测试网状网络，信号很好。",
 "한국어와 漢字를 섞어서 씁니다","日本語とEnglishを混ぜて書くこともあるよね","Hello from Kyiv / Привіт з Києва 🇺🇦",
 "Привет! Hello! こんにちは! 안녕하세요!","Ελληνικά, русский, 日本語, English: all welcome here 🌍","(╯°□°)╯︵ ┻━┻ lol",
 "ヽ(°〇°)ﾉ wow ʘ‿ʘ ᕦ(ò_óˇ)ᕤ","ʕ•ᴥ•ʔ hi there","┌─────┐ │ MESH │ └─────┘","Ⓗⓔⓛⓛⓞ 𝓯𝓻𝓲𝓮𝓷𝓭𝓼","𝕋𝕖𝕤𝕥 𝕞𝕖𝕤𝕤𝕒𝕘𝕖",
 "∑ x² = 42 ≈ π·13.37","Δt = 3.2 s, λ = 868 MHz ✓","Việt Nam xin chào các bạn","Merhaba arkadaşlar, İstanbul'dan selamlar",
 "שלום לכולם","مرحبا بالجميع","नमस्ते दोस्तों","สวัสดีครับ","Árvíztűrő tükörfúrógép 🚿","WX: ☀️ 18°C, wind NW 3 Bft",
 "Signal check ✅ SNR -7.5 dB RSSI -112","¯\\_(ツ)_/¯ no idea","→→→ path: A7 > 2F > 9D ←←←","🄼🄴🅂🄷 🄲🄾🅁🄴","ＭｅｓｈＣｏｒｅ　テスト中です",
 "UR5ABC Київ → Warszawa → Berlin","Zoë's café is open, tot straks!","TÜV-geprüft, Größe: XL, Preis 9€","😂😂😂 brilliant mate 👍🏻"]
for g in GOOD: check(not sg.is_garbage(g),"genuine marked garbage: "+g)
def junk(n):
    out=[chr(random.choice([random.randint(0x21,0x7e),random.randint(0xa0,0x24f),random.randint(0x370,0x4ff),random.randint(0x2500,0x25ff),random.randint(0x3040,0x30ff),random.randint(0x1f300,0x1f64f),random.randint(0x2190,0x23ff)])) for _ in range(n)]
    b=bytearray("".join(out).encode())
    for _ in range(random.randint(0,6)): b.insert(random.randint(0,len(b)),random.randint(0x80,0xff))
    return bytes(b).decode("utf-8","replace")
def raw(n): return bytes(random.randint(1,255) for _ in range(n)).decode("utf-8","replace")
for f in (junk,raw):
    rate=sum(sg.is_garbage(f(random.randint(12,45))) for _ in range(1000))/1000
    check(rate>=0.85,f"{f.__name__} flood caught {rate:.0%}")
# end to end: a slow flood of made-up names through repeater D3
m=mock(); g=guard(m); g.apply_settings({"mode":"protect"})
m.add("Hilltop Hiker","Morning all, clear skies up here",["A7","2F"],ago=4000)
g.poll_once(); g.last_sync=0; g.sync_pending=True; g.poll_once()
first=["Brook","Daan","Femke","Joris","Lotte","Mees","Noor","Sanne","Thijs","Wout"]
for i,n in enumerate(first):
    m.add(f"{n}{random.randint(10,2020)}{random.choice('_.-')}{''.join(random.choice('0123456789abcdef') for _ in range(random.choice((4,5))))}",
          junk(random.randint(14,40)),["D3","2F"],ago=900-i*90)
m.add("Hilltop Hiker",raw(20),["A7","2F"],ago=100)  # a regular whose radio garbles one message
g.poll_once(); g.poll_once()
evs={e.sender:e for e in g.events}
check(sum(e.garbage for e in g.events)>=8,"most of the flood marked garbage: "+str(sum(e.garbage for e in g.events)))
check(not evs["Hilltop Hiker"].garbage and not evs["Hilltop Hiker"].random,"known regular never counted")
hb=g.blocks.get("hop:D3")
check(hb is not None,"repeater D3 blocked: "+str(list(g.blocks)))
check(hb and "unreadable" in (hb.get("reason") or ""),"reason mentions unreadable text: "+str(hb and hb.get("reason")))
check("hop:A7" not in g.blocks,"regular's repeater not blocked")
check(sg.is_garbage("ab\U00084a25c"),"unassigned-plane character counts even when short")
check(not sg.is_garbage("Kan iemand iets zinnigs zeggen over die rare berichten?"),"people talking about the flood are fine")
g.apply_settings({"detect_garbage":False})
e=sg.Event(time.time(),["D3"],"Noor77_ab12",junk(30),"Public")
check(e.garbage,"Event spots garbage")
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
