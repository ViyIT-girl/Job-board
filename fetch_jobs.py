import time,email.utils,sys,html
import json,re,os,urllib.request,urllib.parse,urllib.error
import xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from eligibility import classify
C=json.load(open("config.json"));NOW=datetime.now(timezone.utc)
CUR=None;errs=defaultdict(list);bad=Counter()
CO={k:list(C.get(k,[])) for k in("greenhouse","lever","ashby","workable","recruitee","smartrecruiters","teamtailor","personio","breezy")}
PATS=[(r"boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)","greenhouse"),(r"jobs\.lever\.co/([^/?#]+)","lever"),(r"jobs\.ashbyhq\.com/([^/?#]+)","ashby"),(r"apply\.workable\.com/([^/?#]+)","workable"),(r"([a-z0-9-]+)\.recruitee\.com","recruitee"),(r"(?:careers|jobs)\.smartrecruiters\.com/([^/?#]+)","smartrecruiters"),(r"([a-z0-9-]+)\.teamtailor\.com","teamtailor"),(r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)","personio"),(r"([a-z0-9-]+)\.breezy\.hr","breezy")]
BADURL=[]
for u in C.get("company_urls",[]):
    for pat,k in PATS:
        m=re.search(pat,u,re.I)
        if m:
            if m.group(1) not in CO[k]: CO[k].append(m.group(1))
            break
    else: BADURL.append(u);print("unrecognised careers URL:",u)
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
    for u in ["https://remoteok.com/api"]+["https://remoteok.com/api?tag="+enc(t) for t in C.get("remoteok_tags",[])]:
        for j in (J(u) or [])[1:]:
            add("RemoteOK",j.get("position"),j.get("company"),j.get("url"),j.get("location") or "Remote",j.get("date"),j.get("description"))
def workingnomads():
    d=J("https://www.workingnomads.com/api/exposed_jobs/") or []
    if isinstance(d,dict): d=d.get("results") or d.get("jobs") or []
    for j in d:
        add("WorkingNomads",j.get("title"),j.get("company_name") or j.get("companyName"),j.get("url"),j.get("location") or "",j.get("pub_date") or j.get("pubDate"),j.get("description"))
def plain(s): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",html.unescape(s or ""))).strip()
def hn_hiring():
    hits=(J("https://hn.algolia.com/api/v1/search?query=who%20is%20hiring&tags=story,author_whoishiring&hitsPerPage=5") or {}).get("hits",[])
    threads=[h for h in hits if (h.get("title") or "").lower().startswith("ask hn: who is hiring")][:1]
    for th in threads:
        sid=str(th.get("objectID"));pages=1;pg=0
        while pg<min(pages,3):
            d=J(f"https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{sid}&hitsPerPage=1000&page={pg}") or {}
            pages=d.get("nbPages",1);pg+=1
            for c in d.get("hits",[]):
                if str(c.get("parent_id"))!=sid: continue
                raw=c.get("comment_text") or ""
                segs=[plain(x) for x in plain_head(raw).split("|")]
                role=next((s for s in segs[1:] if any(t in s.lower() for t in C["targets"])),None)
                if not role or len(segs)<3: continue
                loc=" | ".join(s for s in segs[1:] if s!=role)[:160]
                add("HackerNews",role[:150],segs[0][:80],"https://news.ycombinator.com/item?id="+str(c.get("objectID")),loc,c.get("created_at"),plain(raw))
def plain_head(raw): return re.split(r"<p>|<br\s*/?>",html.unescape(raw) if "&lt;p&gt;" in raw else raw,1)[0]
def greenhouse():
    for s in CO["greenhouse"]:
        for j in (J(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true") or {}).get("jobs",[]):
            add("Greenhouse",j.get("title"),s,j.get("absolute_url"),(j.get("location") or {}).get("name"),j.get("first_published") or j.get("updated_at"),j.get("content"),True)
def lever():
    for s in CO["lever"]:
        for j in J(f"https://api.lever.co/v0/postings/{s}?mode=json") or []:
            add("Lever",j.get("text"),s,j.get("hostedUrl"),(j.get("categories") or {}).get("location"),j.get("createdAt"),j.get("descriptionPlain"),True)
def ashby():
    for s in CO["ashby"]:
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
    for s in CO["workable"]:
        for j in (J(f"https://apply.workable.com/api/v1/widget/accounts/{s}?details=true") or {}).get("jobs",[]):
            loc="Remote" if j.get("telecommuting") else ", ".join(x for x in [j.get("city"),j.get("country")] if x)
            add("Workable",j.get("title"),s,j.get("url") or j.get("shortlink"),loc,j.get("published_on") or j.get("created_at"),j.get("description"),True)
def rss_jobs(src,url,direct=False,co=None):
    r=get(url)
    if not r or getattr(r,"status",0)!=200: return
    try: items=list(ET.fromstring(r.read()).iter("item"))
    except Exception: errs[src].append("parse");return
    for it in items:
        t=(it.findtext("title") or "").strip();c=co or ""
        if not co:
            m=re.match(r"^(.{2,60}?):\s+(.+)$",t) or None
            if m: c,t=m.group(1),m.group(2)
            else:
                m=re.match(r"^(.+?)\s+at\s+(.{2,60})$",t)
                if m: t,c=m.group(1),m.group(2)
        try: d=email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        except Exception: d=it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")
        add(src,t,c,it.findtext("link"),it.findtext("region") or "",d,it.findtext("description"),direct)
def recruitee():
    for s in CO["recruitee"]:
        for j in (J(f"https://{s}.recruitee.com/api/offers/") or {}).get("offers",[]):
            loc=j.get("location") or ", ".join(x for x in [j.get("city"),j.get("country")] if x)
            add("Recruitee",j.get("title"),j.get("company_name") or s,j.get("careers_url"),("Remote " if j.get("remote") else "")+loc,j.get("published_at") or j.get("created_at"),j.get("description"),True)
def smartrecruiters():
    for s in CO["smartrecruiters"]:
        for j in (J(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=100") or {}).get("content",[]):
            l=j.get("location") or {}
            loc=("Remote " if l.get("remote") else "")+", ".join(x for x in [l.get("city"),l.get("country")] if x)
            add("SmartRecruiters",j.get("name"),(j.get("company") or {}).get("name") or s,f"https://jobs.smartrecruiters.com/{s}/{j.get('id')}",loc,j.get("releasedDate"),"",True)
def teamtailor():
    for s in CO["teamtailor"]: rss_jobs("Teamtailor",f"https://{s}.teamtailor.com/jobs.rss",True,s)
def personio():
    for s in CO["personio"]:
        r=get(f"https://{s}.jobs.personio.de/xml")
        if not r or getattr(r,"status",0)!=200: continue
        try: ps=list(ET.fromstring(r.read()).iter("position"))
        except Exception: errs["Personio"].append("parse");continue
        for p in ps:
            add("Personio",p.findtext("name"),s,f"https://{s}.jobs.personio.de/job/{p.findtext('id')}",p.findtext("office") or "",p.findtext("createdAt"),"  ".join(v.text or "" for v in p.iter("value")),True)
def breezy():
    for s in CO["breezy"]:
        for j in J(f"https://{s}.breezy.hr/json") or []:
            add("Breezy",j.get("name"),(j.get("company") or {}).get("name") or s,j.get("url"),(j.get("location") or {}).get("name") or "",j.get("published_date"),j.get("description"),True)
SOURCES=[("Remotive",remotive),("Arbeitnow",arbeitnow),("RemoteOK",remoteok),("Greenhouse",greenhouse),("Lever",lever),("Ashby",ashby),("Reddit",reddit),("WeWorkRemotely",wwr),("Himalayas",himalayas),("Jobicy",jobicy),("Workable",workable),("WorkingNomads",workingnomads),("HackerNews",hn_hiring),("Recruitee",recruitee),("SmartRecruiters",smartrecruiters),("Teamtailor",teamtailor),("Personio",personio),("Breezy",breezy)]
for fd in C.get("rss_feeds",[]): SOURCES.append((fd["name"],lambda fd=fd:rss_jobs(fd["name"],fd["url"])))
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
cands=[]
D=Counter();E=Counter()
def ok_url(u):
    try:
        p=urllib.parse.urlsplit(u);return p.scheme in("http","https") and bool(p.netloc)
    except Exception: return False
REQ=("source","title","company","url","location","direct","open","eligibility","evidence","conflict","score","salary_hint","posted","first_seen","desc")
for j in jobs:
    if not ok_url(j["url"]) or not 3<=len(j["title"])<=200: D["invalid"]+=1; continue
    t=j["title"].lower()
    if not any(x in t for x in C["targets"]) or any(x in t for x in C["exclude_title"]): D["title"]+=1; continue
    if not j["date"] or NOW-j["date"]>timedelta(days=C["max_age_days"]): D["age"]+=1; continue
    el=classify(j["location"],j["desc"],j["title"])
    j.update(eligibility=el["status"],evidence=el["evidence"],conflict=el["conflict"],open=el["status"]=="confirmed")
    E[el["status"]]+=1
    cands.append(j)
LEGAL=re.compile(r"\b(inc|llc|ltd|gmbh|corp|corporation|co|limited|plc|sa|bv|ag)\b")
def nco(s): return re.sub(r"[^a-z0-9]","",LEGAL.sub(" ",re.sub(r"[^a-z0-9 ]"," ",(s or "").lower())))
def nti(s): return re.sub(r"[^a-z0-9]","",re.sub(r"\b(remote|hiring)\b"," ",(s or "").lower()))
def nurl(u):
    p=urllib.parse.urlsplit(u or "");h=p.netloc.lower()
    return (h[4:] if h.startswith("www.") else h)+p.path.rstrip("/").lower()
ELR={"confirmed":2,"excluded":2,"verify":0}
def rank(j): return (ELR[j["eligibility"]],int(j["direct"]),j["date"])
groups=[];idx={}
for j in cands:
    keys=["u:"+nurl(j["url"])]
    if j["source"]!="Reddit" and nco(j["company"]): keys.append("c:"+nco(j["company"])+"|"+nti(j["title"]))
    gid=next((idx[k] for k in keys if k in idx),None)
    if gid is None: gid=len(groups);groups.append({"best":j,"all":[j]})
    else:
        g=groups[gid];g["all"].append(j);D["duplicate"]+=1
        if rank(j)>rank(g["best"]): g["best"]=j
    for k in keys: idx[k]=gid
keep=[]
for g in groups:
    b=g["best"];sts={x["eligibility"] for x in g["all"]}
    b["also_on"]=sorted({x["source"] for x in g["all"]}-{b["source"]})
    if {"confirmed","excluded"}<=sts:
        b.update(eligibility="verify",conflict=True,open=False,evidence=(b["evidence"]+["Sources disagree about eligibility"])[:4])
    keep.append(b)
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
    if any(k not in j for k in REQ): D["invalid"]+=1; continue
    out.append(j)
out.sort(key=lambda j:(j["score"],j["posted"]),reverse=True)
json.dump({"schema":1,"updated":NOW.isoformat(),"unrecognised_urls":BADURL,"sources":health,"stats":{"raw":len(jobs),"kept":len(out)},"jobs":out},open("jobs.json","w"),indent=1)
print(len(out),"jobs saved")
