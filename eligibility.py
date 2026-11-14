"""Nigeria eligibility engine. classify(location, description) -> dict(status, evidence, conflict).
status: confirmed (explicitly open, no conflict) | verify (not enough evidence, or conflicting) | excluded (explicit or location-based restriction)."""
import re
FL=re.I
LOC_POS=re.compile(r"nigeria|\b(lagos(?!,?\s*portugal)|abuja|ibadan|port harcourt|kaduna|enugu|benin city|lekki|ikoyi|victoria island)\b|(?<!south )(?<!east )(?<!north )(?<!central )(?<!southern )africa|worldwide|world-wide|anywhere|global|any country|all countries",FL)
DESC_POS=re.compile(r"(applicants?|candidates?|hir\w+|open to|residents? of)[^.\n]{0,50}?\b(nigeria|(?<!south )africa|worldwide|globally|anywhere|around the world)\b|\b(based|located|residing|living) in[^.\n]{0,30}\b(nigeria|(?<!south )africa)\b|\b(anywhere in the world|work from anywhere|fully global|global(?:ly)? remote|worldwide remote)\b",FL)
NEG_NIGERIA=re.compile(r"\b(not|no|cannot|can't|unable|excluding|except|ineligible|outside)\b[^.\n]{0,60}nigeria|nigeria[^.\n]{0,40}(not (eligible|supported|available|accepted)|excluded|ineligible)",FL)
PLACE=r"(us|u\.s\.|usa|united states|uk|united kingdom|canada|australia|eu|europe|european union|north america|latin america|latam|india|germany|france|spain|netherlands|ireland|brazil|mexico|philippines|poland|portugal|israel|uae|singapore|asia|apac|new zealand)"
NEG_ONLY=re.compile(r"\b"+PLACE+r"(?!\w)(\s+only|\s+residents?\b|\s+citizens?\b|[- ]based\s+(candidates|applicants|only))|\b(us|u\.s\.|united states)\s+work\s+authori[sz]ation",FL)
MUST_BE=re.compile(r"(must|need to|required to|have to)\s+(be\s+)?(located|based|reside|live|living|residing|resident|physically located)\s+(in|within)\s+(the\s+)?([a-z][a-z .,'&/-]{2,40})",FL)
AUTH=re.compile(r"(authori[sz]ed|eligible|legally entitled|right) to work (in|within) (the )?([a-z][a-z .'&/-]{1,30})",FL)
REMOTE_IN=re.compile(r"\b(anywhere|remote(?:ly)?|work remotely)\s+(in|within|from)\s+(the\s+)?"+PLACE+r"(?!\w)",FL)
REGION_AFTER=re.compile(r"\s+(in|within|from)\s+(the\s+)?"+PLACE+r"(?!\w)",FL)
PLACE_T=PLACE[:-1]+"|emea)"
TITLE_NEG=re.compile(r"[-\u2013\u2014(\[,|/]\s*"+PLACE_T+r"(?!\w)|\b"+PLACE_T+r"(?!\w)\s*(only|-based)",FL)
TITLE_POS=re.compile(r"worldwide|anywhere|remote\s*/\s*global|global\s+remote",FL)
OK_PLACE=re.compile(r"nigeria|africa|worldwide|anywhere|global|any country",FL)
FILLER=re.compile(r"\b(remote|hybrid|fully|work from home|wfh|flexible|telecommute)\b|[^a-z ]",FL)
def snip(m,text):
    s=re.sub(r"\s+"," ",text[max(0,m.start()-15):m.end()+25]).strip()
    return s[:100]
def classify(location,description,title=""):
    loc=location or "";desc=description or "";ttl=title or ""
    pos=[];neg=[];tneg=[];hard=False
    m=TITLE_POS.search(ttl)
    if m: pos.append("Title: "+ttl[:70])
    m=TITLE_NEG.search(ttl)
    if m: tneg.append("Title suggests a region: "+ttl[:70])
    if LOC_POS.search(loc): pos.append("Location: "+loc[:60])
    for m in DESC_POS.finditer(desc):
        if REGION_AFTER.match(desc,m.end()): continue
        pos.append("Description: "+snip(m,desc))
        break
    for m in REMOTE_IN.finditer(desc):
        neg.append("Description: "+snip(m,desc));break
    for m in NEG_NIGERIA.finditer(desc):
        neg.append("Description: "+snip(m,desc));hard=True;break
    for m in NEG_ONLY.finditer(desc):
        neg.append("Description: "+snip(m,desc));break
    for m in MUST_BE.finditer(desc):
        if not OK_PLACE.search(m.group(6)): neg.append("Description: "+snip(m,desc));break
    for m in AUTH.finditer(desc):
        if not OK_PLACE.search(m.group(4)): neg.append("Description: "+snip(m,desc));break
    rest=FILLER.sub(" ",loc).strip()
    if rest and not LOC_POS.search(loc) and "emea" not in rest.lower():
        neg.append("Location lists only: "+loc[:60])
    if hard: status,conflict="excluded",False
    elif pos and (neg or tneg): status,conflict="verify",True
    elif neg: status,conflict="excluded",False
    elif tneg: status,conflict="verify",False
    elif pos: status,conflict="confirmed",False
    else: status,conflict="verify",False
    return {"status":status,"evidence":(pos+neg+tneg)[:4],"conflict":conflict}
