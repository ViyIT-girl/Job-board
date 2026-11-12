import sys,os,io,json,tempfile,time,unittest,urllib.request,urllib.error,runpy,email.utils
from datetime import datetime,timezone
sys.path.insert(0,os.path.dirname(__file__))
from test_pipeline import run_pipeline,NOW,ROOT
def rem(url="https://ok.test/1",title="Executive Assistant",co="Acme"):
    return {"jobs":[{"title":title,"company_name":co,"url":url,"candidate_required_location":"Worldwide","publication_date":NOW,"description":"x"}]}
class J(unittest.TestCase):
    def test_bad_url_schemes_dropped(self):
        for u in ["javascript:alert(1)","data:text/html,hi","ftp://x.test/1","not a url"]:
            code,out=run_pipeline({"remotive.com":rem(u)})
            self.assertEqual(code,0)
            self.assertEqual(out["jobs"],[],u)
    def test_overlong_title_dropped(self):
        code,out=run_pipeline({"remotive.com":rem(title="Executive Assistant "+"x"*300)})
        self.assertEqual(out["jobs"],[])
    def test_valid_record_has_all_fields_and_schema(self):
        code,out=run_pipeline({"remotive.com":rem()})
        self.assertEqual(out["schema"],1);self.assertEqual(len(out["jobs"]),1)
        for k in ("source","title","company","url","location","direct","open","eligibility","evidence","conflict","score","salary_hint","posted","first_seen","desc"):
            self.assertIn(k,out["jobs"][0])
class R(io.BytesIO): status=200
class F(unittest.TestCase):
    def test_funding_rejects_bad_links(self):
        now=email.utils.format_datetime(datetime.now(timezone.utc))
        rss=("<rss><channel>"+"".join(f"<item><title>{c} AI raises $5M seed round</title><link>{l}</link><pubDate>{now}</pubDate></item>" for c,l in [("Acme","javascript:alert(1)"),("Beta","https://t.test/b")])+"</channel></rss>").encode()
        d=tempfile.mkdtemp();ro,cwd=urllib.request.urlopen,os.getcwd()
        urllib.request.urlopen=lambda req,timeout=None:R(rss);os.chdir(d)
        try: runpy.run_path(os.path.join(ROOT,"fetch_funding.py"))
        finally: urllib.request.urlopen=ro;os.chdir(cwd)
        out=json.load(open(os.path.join(d,"funding.json")))
        self.assertEqual([c["company"] for c in out["companies"]],["Beta AI"]);self.assertEqual(out["schema"],1)
if __name__=="__main__": unittest.main()
