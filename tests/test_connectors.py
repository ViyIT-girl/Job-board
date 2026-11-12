import sys,os,time,unittest,email.utils
from datetime import datetime,timezone
sys.path.insert(0,os.path.dirname(__file__))
from test_pipeline import run_pipeline,NOW
RFC=email.utils.format_datetime(datetime.now(timezone.utc))
def rss(*items): return ("<rss><channel>"+"".join(f"<item><title>{t}</title><link>{l}</link><pubDate>{RFC}</pubDate><description>Hiring worldwide</description></item>" for t,l in items)+"</channel></rss>").encode()
PERSONIO=f"<workzag-jobs><position><id>7</id><name>Business Operations Associate</name><office>Remote</office><createdAt>{NOW}</createdAt><jobDescriptions><jobDescription><name>About</name><value>Join us</value></jobDescription></jobDescriptions></position></workzag-jobs>".encode()
CFG={"greenhouse":[],"ashby":[],"workable":[],"lever":[],"remotive_searches":[],"reddit":[],"remoteok_tags":[],
 "company_urls":["https://acme.recruitee.com","https://careers.smartrecruiters.com/AcmeSR","https://acme.teamtailor.com","https://acme.jobs.personio.de","https://acme.breezy.hr","https://jobs.lever.co/acmelever","https://example.com/careers"],
 "rss_feeds":[{"name":"MyBoard","url":"https://feed.test/rss"}]}
ROUTES={
 "acme.recruitee.com/api/offers":{"offers":[{"title":"Executive Assistant","careers_url":"https://acme.recruitee.com/o/ea","location":"Remote","published_at":NOW,"description":"We are hiring candidates worldwide.","company_name":"Acme Rec"}]},
 "api.smartrecruiters.com/v1/companies/AcmeSR/postings":{"content":[{"id":"1","name":"Operations Coordinator","location":{"remote":True},"releasedDate":NOW,"company":{"name":"Acme SR"}}]},
 "acme.teamtailor.com/jobs.rss":rss(("Chief of Staff","https://acme.teamtailor.com/jobs/1")),
 "acme.jobs.personio.de/xml":PERSONIO,
 "acme.breezy.hr/json":[{"name":"Executive Business Partner","url":"https://acme.breezy.hr/p/b1","published_date":NOW,"location":{"name":"Remote"},"company":{"name":"Acme Breezy"},"description":"x"}],
 "api.lever.co/v0/postings/acmelever":[{"text":"Project Coordinator","hostedUrl":"https://jobs.lever.co/acmelever/1","categories":{"location":"Worldwide"},"createdAt":int(time.time()*1000),"descriptionPlain":"x"}],
 "feed.test/rss":rss(("Virtual Assistant at Gamma","https://feed.test/1"),("Delta: Operations Associate","https://feed.test/2"))}
class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.code,cls.out=run_pipeline(ROUTES,cfg=CFG)
    def test_run_ok_and_bad_url_reported(self):
        self.assertEqual(self.code,0);self.assertEqual(self.out["unrecognised_urls"],["https://example.com/careers"])
    def test_each_platform_returns_its_job(self):
        got={j["source"]:j for j in self.out["jobs"]}
        for src in ["Recruitee","SmartRecruiters","Teamtailor","Personio","Breezy","Lever","MyBoard"]:
            self.assertIn(src,got,src);self.assertEqual(self.out["sources"][src]["status"],"ok",src)
        self.assertEqual(got["Recruitee"]["company"],"Acme Rec")
        self.assertEqual(got["Recruitee"]["eligibility"],"confirmed")
        self.assertIn("jobs.smartrecruiters.com/AcmeSR/1",got["SmartRecruiters"]["url"])
    def test_generic_rss_extracts_company(self):
        r={(j["company"],j["title"]) for j in self.out["jobs"] if j["source"]=="MyBoard"}
        self.assertEqual(r,{("Gamma","Virtual Assistant"),("Delta","Operations Associate")})
if __name__=="__main__": unittest.main()
