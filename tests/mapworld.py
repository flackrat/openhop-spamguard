# A made-up mesh across England for testing where the map puts spam (6.45.0). Random places and keys, nothing real.
import random, math, heapq, collections
def km(a,b):
    la1,lo1,la2,lo2=map(math.radians,(a[0],a[1],b[0],b[1]))
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(h)))
class World:
    def __init__(s,seed=1,n=900,hubs=12,me=(40.2,-95.5)):
        R=random.Random(seed); s.R=R
        s.reps=[]
        for i in range(n):
            lat=R.uniform(38.6,41.6); lon=R.uniform(-98.4,-93.4)
            key=''.join(R.choice('0123456789ABCDEF') for _ in range(64))
            hub=i<hubs
            s.reps.append({"i":i,"key":key,"name":("Hub" if hub else "Rep")+f" {i}","lat":lat,"lon":lon,"range":R.uniform(60,90) if hub else R.uniform(14,26),"hub":hub})
        s.me={"name":"Me","lat":me[0],"lon":me[1],"range":40}
        s.adj=collections.defaultdict(list)
        for a in s.reps:
            for b in s.reps:
                if a is b: continue
                d=km((a["lat"],a["lon"]),(b["lat"],b["lon"]))
                if d<=(a["range"]+b["range"])/2: s.adj[a["i"]].append((b["i"],d))
        s.me_nb=[r["i"] for r in s.reps if km((r["lat"],r["lon"]),me)<=(r["range"]+40)/2]
        # paths to me: fewest hops then shortest, Dijkstra on (hops, km) from me's neighbours outward
        dist={}; prev={}; pq=[]
        for i in s.me_nb:
            dist[i]=(1,km((s.reps[i]["lat"],s.reps[i]["lon"]),me)); heapq.heappush(pq,(dist[i],i)); prev[i]=None
        while pq:
            d,i=heapq.heappop(pq)
            if d>dist[i]: continue
            for j,w in s.adj[i]:
                nd=(d[0]+1,d[1]+w)
                if j not in dist or nd<dist[j]:
                    dist[j]=nd; prev[j]=i; heapq.heappush(pq,(nd,j))
        s.dist=dist; s.prev=prev
    def route(s,i):
        """Repeater codes (1 byte) from repeater i towards me, sender end first."""
        out=[]
        while i is not None:
            out.append(i); i=s.prev[i]
        return out
    def code(s,i,nb=1): return s.reps[i]["key"][:2*nb]
    def path(s,i,nb=1): return [s.code(j,nb) for j in s.route(i)]
    def nearest(s,pt,k=1):
        return sorted((r for r in s.reps if r["i"] in s.dist),key=lambda r:km((r["lat"],r["lon"]),pt))[:k]
