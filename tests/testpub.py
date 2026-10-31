import sys,time,os; sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spamguard import SpamGuard as S
me={"lat":51.455,"lon":-0.971}; radio={"frequency":869618000,"bandwidth":62500,"spreading_factor":8}
now=time.strftime("%Y-%m-%dT%H:%M:%S.000Z",time.gmtime(time.time()-3600))
def n(k,la,lo,adv=now,p={"freq":869.618,"bw":62.5,"sf":8},t=2): return {"public_key":k,"type":t,"adv_name":k[:4],"last_advert":adv,"adv_lat":la,"adv_lon":lo,"updated_date":now,"params":p}
nodes=[n("6FAA"*16,51.07,-0.152),                      # good
 n("6FBB"*16,51.0,-0.142,adv="1969-12-31T23:12:37.000Z"), # no clock -> falls back to updated_date, kept
 n("6FCC"*16,51.0,-0.142,adv="2100-10-22T14:16:53.000Z"), # future -> fallback, kept
 n("6FDD"*16,51.0,-0.142,adv="2024-05-31T07:52:36.000Z"), # stale -> dropped
 n("6FEE"*16,51.0,-0.142,p={"freq":869.618,"bw":62.5,"sf":7}), # other preset -> dropped
 n("6FFF"*16,48.0,11.5),                                # Munich -> too far
 n("29AA"*16,51.0,-0.142,adv="garbage"), n("29BB"*16,51.0,-0.142,p=None),
 n("11"*32,51.0,-0.142,t=1), {"type":2,"public_key":None}, "junk"]
nodes[6]["updated_date"]=None
r=S.parse_public_map(nodes,me,radio=radio); ks=[x["key"][:4] for x in r]; print(ks)
assert ks==["6FAA","6FBB","6FCC","29AA","29BB"],ks
assert r[3]["seen"]==0 and r[0]["seen"]>0
assert len(S.parse_public_map(nodes,me))==6   # no radio known -> keep the sf7 one too
print("ok")
