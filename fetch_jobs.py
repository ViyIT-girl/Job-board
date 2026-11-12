import time,email.utils,sys
import json,re,os,urllib.request,urllib.parse,urllib.error
import xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from eligibility import classify
C=json.load(open("config.json"));NOW=datetime.now(timezone.utc)
CUR=None;errs=defaultdict(list);bad=Counter()
def get(u,method="GET"):
    try:
        r=urllib.request.Request(u,method=method,headers={"User-Agent":"Mozilla/5.0 personal-job-board"})
        return urllib.request.urlopen(r,timeout=20)
    except urllib.error.HTTPError as e:
        if method=="GET":
            loc=e.headers.get("Location","") if 300<=e.code<400 and e.headers else ""
            print("http",e.code,u[:70],loc[:80]);errs[CUR].append(str(e.code))
        return e
    except Exception as e:
        if method=="GET": print("skip",u[:70],e);errs[CUR].append("err")
def J(u):
    r=get(u)
    try: return json.loads(r.read()) if r and r.status==200 else None
    except Exception: return None
def dt(v):
    try:
        if isinstance(v,datetime): return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v,(int,float)): return datetime.fromtimestamp(v/1000 if v>1e11 else v,timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception: return None
jobs=[]
def add(src,t,co,url,loc,date,desc="",direct=False):
    if not t or not url: bad[src]+=1;return
    d=re.sub(r"<[^>]+>|&[a-z]+;"," ",desc or "")
    jobs.append(dict(source=src,title=t,company=co or "",url=url,location=loc or "",date=dt(date),desc=d[:3000],direct=direct))
def enc(q): return urllib.parse.quote(q)
def remotive():
    for q in C["remotive_searches"]:
        for j in (J("https://remotive.com/api/remote-jobs?search="+enc(q)) or {}).get("jobs",[]):
            add("Remotive",j.get("title"),j.get("company_name"),j.get("url"),j.get("candidate_required_location"),j.get("publication_date"),j.get("description"))
def arbeitnow():
    for j in (J("https://www.arbeitnow.com/api/job-board-api") or {}).get("data",[]):
        if j.get("remote"): add("Arbeitnow",j.get("title"),j.get("company_name"),j.get("url"),"Remote "+(j.get("location") or ""),j.get("created_at"),j.get("description"))
def remoteok():
    for j in (J("https://remoteok.com/api") or [])[1:]:
        add("RemoteOK",j.get("position"),j.get("company"),j.get("url"),j.get("location") or "Remote",j.get("date"),j.get("description"))
def greenhouse():
    for s in C["greenhouse"]:
        for j in (J(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true") or {}).get("jobs",[]):
            add("Greenhouse",j.get("title"),s,j.get("absolute_url"),(j.get("location") or {}).get("name"),j.get("first_published") or j.get("updated_at"),j.get("content"),True)
def lever():
    for s in C["lever"]:
        for j in J(f"https://api.lever.co/v0/postings/{s}?mode=json") or []:
            add("Lever",j.get("text"),s,j.get("hostedUrl"),(j.get("categories") or {}).get("location"),j.get("createdAt"),j.get("descriptionPlain"),True)
def ashby():
    for s in C["ashby"]:
        for j in (J(f"https://api.ashbyhq.com/posting-api/job-board/{s}") or {}).get("jobs",[]):
            add("Ashby",j.get("title"),s,j.get("jobUrl"),("Remote " if j.get("isRemote") else "")+(j.get("location") or ""),j.get("publishedAt"),j.get("descriptionPlain"),True)
A="{http://www.w3.org/2005/Atom}"
def reddit():
    for sub in C.get("reddit",[]):
        time.sleep(4)
        r=get(f"https://www.reddit.com/r/{sub}/new/.rss?limit=100")
        if not r or getattr(r,"status",0)!=200: continue
        try: root=ET.fromstring(r.read())
        except Exception: errs["Reddit"].append("parse");continue
        for e in root.iter(A+"entry"):
            l=e.find(A+"link")
            add("Reddit",e.findtext(A+"title"),"r/"+sub,l.get("href") if l is not None else None,"Remote",e.findtext(A+"updated"),e.findtext(A+"content"))
def wwr():
    for u in ["remote-management-and-finance-jobs","all-other-remote-jobs","remote-customer-support-jobs"]:
        r=get(f"https://weworkremotely.com/categories/{u}.rss")
        if not r or getattr(r,"status",0)!=200: continue
        try: items=list(ET.fromstring(r.read()).iter("item"))
        except Exception: errs["WeWorkRemotely"].append("parse");continue
        for it in items:
            co,_,ti=(it.findtext("title") or "").partition(": ")
            try: d=email.utils.parsedate_to_datetime(it.findtext("pubDate"))
            except Exception: d=None
            add("WeWorkRemotely",ti,co,it.findtext("link"),it.findtext("region") or "Remote",d,it.findtext("description"))
def himalayas():
    for q in C["remotive_searches"]:
        for j in (J("https://himalayas.app/jobs/api/search?worldwide=true&q="+enc(q)) or {}).get("jobs",[]):
            add("Himalayas",j.get("title"),j.get("companyName"),j.get("applicationLink") or j.get("guid"),", ".join(j.get("locationRestrictions") or []),j.get("pubDate"),j.get("description"))
def jobicy():
    for q in C["remotive_searches"]:
        for j in (J("https://jobicy.com/api/v2/remote-jobs?count=50&tag="+enc(q)) or {}).get("jobs",[]):
            add("Jobicy",j.get("jobTitle"),j.get("companyName"),j.get("url"),j.get("jobGeo") or "",j.get("pubDate"),j.get("jobDescription"))
def workable():
    for s in C.get("workable",[]):
        for j in (J(f"https://apply.workable.com/api/v1/widget/accounts/{s}?details=true") or {}).get("jobs",[]):
            loc="Remote" if j.get("telecommuting") else ", ".join(x for x in [j.get("city"),j.get("country")] if x)
            add("Workable",j.get("title"),s,j.get("url") or j.get("shortlink"),loc,j.get("published_on") or j.get("created_at"),j.get("description"),True)
SOURCES=[("Remotive",remotive),("Arbeitnow",arbeitnow),("RemoteOK",remoteok),("Greenhouse",greenhouse),("Lever",lever),("Ashby",ashby),("Reddit",reddit),("WeWorkRemotely",wwr),("Himalayas",himalayas),("Jobicy",jobicy),("Workable",workable)]
health={}
for name,fn in SOURCES:
    CUR=name;crash=None
    try: fn()
    except Exception as e: crash=type(e).__name__+": "+str(e)[:80];print("source crashed",name,crash)
    raw=sum(1 for j in jobs if j["source"]==name);codes=sorted(set(errs[name]))
    st="failed" if raw==0 and (crash or codes) else "partial" if (crash or codes) else "ok" if raw else "empty"
    health[name]={"status":st,"raw":raw,"errors":codes[:5]+([crash] if crash else []),"invalid":bad[name]}
CUR=None
print("source health:",{k:v["status"]+":"+str(v["raw"]) for k,v in health.items()})
if not jobs:
    print("No jobs collected from any source; keeping previous data.");sys.exit(1)
try: old={j["url"]:j for j in json.load(open("jobs.json"))["jobs"]}
except Exception: old={}
seen,keep=set(),[]
D=Counter();E=Counter()
for j in jobs:
    t=j["title"].lower()
    if not any(x in t for x in C["targets"]) or any(x in t for x in C["exclude_title"]): D["title"]+=1; continue
    if not j["date"] or NOW-j["date"]>timedelta(days=C["max_age_days"]): D["age"]+=1; continue
    el=classify(j["location"],j["desc"],j["title"])
    j.update(eligibility=el["status"],evidence=el["evidence"],conflict=el["conflict"],open=el["status"]=="confirmed")
    E[el["status"]]+=1
    k=(j["company"].lower(),t)
    if k in seen: D["duplicate"]+=1; continue
    seen.add(k);keep.append(j)
print("dropped:",dict(D));print("eligibility (before dedupe):",dict(E))
def alive(j):
    r=get(j["url"],"HEAD");return not(r and getattr(r,"status",getattr(r,"code",200)) in(404,410))
with ThreadPoolExecutor(10) as ex: ok=list(ex.map(alive,keep))
out=[]
for j,a in zip(keep,ok):
    if not a: continue
    sal=re.search(r"\$\s?\d{2,3}",j["desc"]) is not None
    j["score"]=2*j["direct"]+2*j["open"]+sal-(3 if j["eligibility"]=="excluded" else 0)
    j["salary_hint"]=sal;j["posted"]=j.pop("date").date().isoformat()
    j["first_seen"]=old.get(j["url"],{}).get("first_seen",NOW.date().isoformat())
    j["desc"]=j["desc"][:300]
    out.append(j)
out.sort(key=lambda j:(j["score"],j["posted"]),reverse=True)
json.dump({"updated":NOW.isoformat(),"sources":health,"stats":{"raw":len(jobs),"kept":len(out)},"jobs":out},open("jobs.json","w"),indent=1)
print(len(out),"jobs saved")
