import json,re,os,urllib.request,urllib.parse
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
C=json.load(open("config.json"));NOW=datetime.now(timezone.utc)
def get(u,method="GET"):
    try:
        r=urllib.request.Request(u,method=method,headers={"User-Agent":"Mozilla/5.0 personal-job-board"})
        return urllib.request.urlopen(r,timeout=20)
    except urllib.error.HTTPError as e: return e
    except Exception as e: print("skip",u,e)
def J(u):
    r=get(u)
    try: return json.loads(r.read()) if r and r.status==200 else None
    except Exception: return None
def dt(v):
    try:
        if isinstance(v,(int,float)): return datetime.fromtimestamp(v/1000 if v>1e11 else v,timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception: return None
jobs=[]
def add(src,t,co,url,loc,date,desc="",direct=False):
    d=re.sub(r"<[^>]+>|&[a-z]+;"," ",desc or "")
    jobs.append(dict(source=src,title=t or "",company=co or "",url=url,location=loc or "",date=dt(date),desc=d[:3000],direct=direct))
for q in C["remotive_searches"]:
    for j in (J("https://remotive.com/api/remote-jobs?search="+urllib.parse.quote(q)) or {}).get("jobs",[]):
        add("Remotive",j["title"],j["company_name"],j["url"],j.get("candidate_required_location"),j.get("publication_date"),j.get("description"))
for j in (J("https://www.arbeitnow.com/api/job-board-api") or {}).get("data",[]):
    if j.get("remote"): add("Arbeitnow",j["title"],j["company_name"],j["url"],"Remote "+j.get("location",""),j.get("created_at"),j.get("description"))
for j in (J("https://remoteok.com/api") or [])[1:]:
    add("RemoteOK",j.get("position"),j.get("company"),j.get("url"),j.get("location") or "Remote",j.get("date"),j.get("description"))
for s in C["greenhouse"]:
    for j in (J(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true") or {}).get("jobs",[]):
        add("Greenhouse",j["title"],s,j["absolute_url"],j["location"]["name"],j.get("updated_at"),j.get("content"),True)
for s in C["lever"]:
    for j in J(f"https://api.lever.co/v0/postings/{s}?mode=json") or []:
        add("Lever",j["text"],s,j["hostedUrl"],j["categories"].get("location"),j.get("createdAt"),j.get("descriptionPlain"),True)
for s in C["ashby"]:
    for j in (J(f"https://api.ashbyhq.com/posting-api/job-board/{s}") or {}).get("jobs",[]):
        add("Ashby",j["title"],s,j["jobUrl"],("Remote " if j.get("isRemote") else "")+(j.get("location") or ""),j.get("publishedAt"),j.get("descriptionPlain"),True)
import xml.etree.ElementTree as ET
A="{http://www.w3.org/2005/Atom}"
for sub in C.get("reddit",[]):
    r=get(f"https://www.reddit.com/r/{sub}/new/.rss?limit=100")
    if not r or getattr(r,"status",0)!=200: continue
    try: root=ET.fromstring(r.read())
    except Exception: continue
    for e in root.iter(A+"entry"):
        add("Reddit",e.findtext(A+"title"),"r/"+sub,e.find(A+"link").get("href"),"Remote (Reddit post)",e.findtext(A+"updated"),e.findtext(A+"content"))
RESTRICT=re.compile(r"(\bus\b|u\.s\.|united states|usa|\buk\b|canada|\beu\b|europe|north america|emea|latam|india)( only|-based| residents| citizens)|must (be )?(located|reside|based|live) in|us citizens?|authorized to work in the (us|united states)",re.I)
OPEN=re.compile(r"nigeria|africa|worldwide|anywhere|global|world-wide",re.I)
old={j["url"]:j for j in json.load(open("jobs.json"))["jobs"]} if os.path.exists("jobs.json") else {}
seen,keep=set(),[]
for j in jobs:
    t=j["title"].lower()
    if not any(x in t for x in C["targets"]) or any(x in t for x in C["exclude_title"]): continue
    if not j["date"] or NOW-j["date"]>timedelta(days=C["max_age_days"]): continue
    if not j["direct"] and "remote" not in (j["location"]+t+j["desc"][:600]).lower() and not OPEN.search(j["location"]): continue
    blob=j["location"]+" "+j["desc"]
    j["open"]=bool(OPEN.search(j["location"]) or re.search(r"nigeria|work from anywhere|worldwide",j["desc"],re.I))
    if (RESTRICT.search(blob) or re.search(r"\b(usa?|united states|canada|uk)\b",j["location"],re.I) and not j["open"]) and not j["open"]: continue
    k=(j["company"].lower(),t)
    if k in seen: continue
    seen.add(k);keep.append(j)
def alive(j):
    r=get(j["url"],"HEAD");return not(r and getattr(r,"status",getattr(r,"code",200)) in(404,410))
with ThreadPoolExecutor(10) as ex: ok=list(ex.map(alive,keep))
out=[]
for j,a in zip(keep,ok):
    if not a: continue
    sal=re.search(r"\$\s?\d{2,3}",j["desc"]) is not None
    j["score"]=2*j["direct"]+2*j["open"]+sal
    j["salary_hint"]=sal;j["posted"]=j.pop("date").date().isoformat()
    j["first_seen"]=old.get(j["url"],{}).get("first_seen",NOW.date().isoformat())
    j["desc"]=j["desc"][:300]
    out.append(j)
out.sort(key=lambda j:(-j["score"],j["posted"]),reverse=False)
out.sort(key=lambda j:(j["score"],j["posted"]),reverse=True)
json.dump({"updated":NOW.isoformat(),"jobs":out},open("jobs.json","w"),indent=1)
print(len(out),"jobs saved")
