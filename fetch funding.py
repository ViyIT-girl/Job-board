import json,re,os,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone,timedelta
NOW=datetime.now(timezone.utc)
Q=["raises seed SaaS","raises seed AI startup","raises pre-seed","raises Series A fintech","raises Series A healthtech","raises Series A AI","raises Series B SaaS","raises seed fintech","raises seed healthtech","raises seed B2B software"]
FEEDS=["https://techcrunch.com/category/venture/feed/","https://www.finsmes.com/feed"]+["https://news.google.com/rss/search?q="+urllib.parse.quote(q+" when:14d")+"&hl=en-US&gl=US&ceid=US:en" for q in Q]
RX=re.compile(r"^(?P<co>[A-Z0-9][\w.&' -]{1,40}?)\s+(?:raises|raised|secures|lands|closes|bags|nabs|snags|scores|gets)\s+(?:an?\s+)?(?:US)?[$€£]\s?(?P<n>[\d.,]+)\s?(?P<u>million|billion|[MBK])?",re.I)
STAGE=re.compile(r"pre-?seed|seed|series [abcd]\b",re.I)
SECTOR=re.compile(r"\b(ai|saas|fintech|health\w*|software|b2b|cloud|data|payments?|automation|security|platform|agents?)\b",re.I)
def amt(n,u):
    try: v=float(n.replace(",",""))
    except: return None
    u=(u or "").lower();return v*(1000 if u.startswith("b") else 0.001 if u=="k" else 1)
old={c["company"].lower():c for c in json.load(open("funding.json"))["companies"]} if os.path.exists("funding.json") else {}
found={}
for f in FEEDS:
    try:
        root=ET.fromstring(urllib.request.urlopen(urllib.request.Request(f,headers={"User-Agent":"Mozilla/5.0"}),timeout=20).read())
    except Exception as e: print("skip",f[:60],e);continue
    for it in root.iter("item"):
        title=re.sub(r"\s+-\s+[^-]+$","",(it.findtext("title") or "").strip())
        m=RX.match(title)
        if not m: continue
        try: d=parsedate_to_datetime(it.findtext("pubDate"))
        except: continue
        if NOW-d>timedelta(days=21): continue
        st=STAGE.search(title);a=amt(m["n"],m["u"])
        stage=st.group(0).title() if st else ""
        if stage.lower().startswith(("series c","series d")): continue
        if not stage and (a is None or a>25): continue
        if not SECTOR.search(title): continue
        co=m["co"].strip(" -");k=co.lower()
        if k in found and found[k]["date"]>=d.date().isoformat(): continue
        found[k]=dict(company=co,stage=stage or "Early",amount=f"${m['n']}{(m['u'] or 'M')[0].upper()}",date=d.date().isoformat(),headline=title,link=it.findtext("link"),first_seen=old.get(k,{}).get("first_seen",NOW.date().isoformat()))
out=sorted(found.values(),key=lambda c:c["date"],reverse=True)
json.dump({"updated":NOW.isoformat(),"companies":out},open("funding.json","w"),indent=1)
print(len(out),"funded companies")
