import sys,os,time,unittest
sys.path.insert(0,os.path.dirname(__file__))
from test_pipeline import run_pipeline,NOW
def rem(url,loc="Worldwide",title="Executive Assistant",co="Acme, Inc.",desc="Join us."):
    return {"jobs":[{"title":title,"company_name":co,"url":url,"candidate_required_location":loc,"publication_date":NOW,"description":desc}]}
def arb(url,title="Executive Assistant",co="ACME",desc="",loc=""):
    return {"data":[{"title":title,"company_name":co,"url":url,"remote":True,"location":loc,"created_at":int(time.time()),"description":desc}]}
class T(unittest.TestCase):
    def test_same_url_different_sources_merged(self):
        code,out=run_pipeline({"remotive.com":rem("https://x.test/job/1?utm=a",co="A"),"arbeitnow.com":arb("https://www.x.test/job/1/",co="B")})
        self.assertEqual(len(out["jobs"]),1);self.assertTrue(out["jobs"][0]["also_on"])
    def test_company_and_title_formatting_merged(self):
        code,out=run_pipeline({"remotive.com":rem("https://a.test/1",title="Executive Assistant (Remote)"),"arbeitnow.com":arb("https://b.test/2")})
        self.assertEqual(len(out["jobs"]),1)
    def test_different_regions_not_merged(self):
        code,out=run_pipeline({"remotive.com":rem("https://a.test/1",title="Project Manager (EMEA)",co="Acme"),"arbeitnow.com":arb("https://b.test/2",title="Project Manager (APAC)",co="Acme")})
        self.assertEqual(len(out["jobs"]),2)
    def test_explicit_evidence_beats_vague(self):
        code,out=run_pipeline({"remotive.com":rem("https://x.test/1",loc="USA Only"),"arbeitnow.com":arb("https://x.test/1",loc="")})
        self.assertEqual(out["jobs"][0]["eligibility"],"excluded")
    def test_disagreeing_sources_flagged(self):
        code,out=run_pipeline({"remotive.com":rem("https://x.test/1",loc="Worldwide"),"arbeitnow.com":arb("https://x.test/1",desc="US only role.")})
        j=out["jobs"][0];self.assertEqual(j["eligibility"],"verify");self.assertTrue(j["conflict"])
    def test_reddit_same_title_different_posts_kept(self):
        feed=("<feed xmlns='http://www.w3.org/2005/Atom'>"+"".join(f"<entry><title>[HIRING] Virtual Assistant</title><link href='https://reddit.com/r/forhire/{i}'/><updated>{NOW}</updated><content>x</content></entry>" for i in (1,2))+"</feed>").encode()
        code,out=run_pipeline({"reddit.com/r/forhire":feed})
        self.assertEqual(len(out["jobs"]),2)
if __name__=="__main__": unittest.main()
