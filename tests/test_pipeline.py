import sys,os,io,json,shutil,tempfile,time,unittest,urllib.request,urllib.error,runpy
from datetime import datetime,timezone
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,ROOT)
NOW=datetime.now(timezone.utc).isoformat()
class R(io.BytesIO): status=200
def run_pipeline(routes,prev=None,cfg=None):
    d=tempfile.mkdtemp()
    shutil.copy(os.path.join(ROOT,"config.json"),d)
    if cfg:
        p=os.path.join(d,"config.json");c=json.load(open(p));c.update(cfg);json.dump(c,open(p,"w"))
    if prev is not None: json.dump(prev,open(os.path.join(d,"jobs.json"),"w"))
    def fake(req,timeout=None):
        for k,v in routes.items():
            if k in req.full_url:
                if isinstance(v,Exception): raise v
                return R(v if isinstance(v,bytes) else json.dumps(v).encode())
        if req.get_method()=="HEAD": return R(b"")
        raise urllib.error.URLError("offline")
    ro,rs,cwd=urllib.request.urlopen,time.sleep,os.getcwd()
    urllib.request.urlopen=fake;time.sleep=lambda x:None;os.chdir(d)
    try:
        try: runpy.run_path(os.path.join(ROOT,"fetch_jobs.py"));code=0
        except SystemExit as e: code=e.code
    finally:
        urllib.request.urlopen,time.sleep=ro,rs;os.chdir(cwd)
    p=os.path.join(d,"jobs.json")
    return code,(json.load(open(p)) if os.path.exists(p) else None)
GOOD={"data":[{"title":"Executive Assistant","company_name":"Zed","url":"https://z.test/1","remote":True,"location":"","created_at":int(time.time()),"description":"We are hiring candidates worldwide."}]}
class T(unittest.TestCase):
    def test_broken_source_does_not_stop_run(self):
        code,out=run_pipeline({"remotive.com":{"jobs":[5]},"arbeitnow.com":GOOD})
        self.assertEqual(code,0)
        self.assertEqual([j["company"] for j in out["jobs"]],["Zed"])
        self.assertEqual(out["sources"]["Remotive"]["status"],"failed")
        self.assertEqual(out["sources"]["Arbeitnow"]["status"],"ok")
    def test_invalid_records_skipped(self):
        bad={"jobs":[{"company_name":"X","url":"https://x.test/1"},{"title":"Executive Assistant","company_name":"Y"}]}
        code,out=run_pipeline({"remotive.com":bad,"arbeitnow.com":GOOD})
        self.assertEqual(code,0);self.assertEqual(len(out["jobs"]),1)
        self.assertGreater(out["sources"]["Remotive"]["invalid"],0)
    def test_all_sources_down_keeps_old_data(self):
        prev={"updated":"x","jobs":[{"url":"https://old.test","title":"Executive Assistant"}]}
        code,out=run_pipeline({},prev)
        self.assertEqual(code,1);self.assertEqual(out,prev)
    def test_first_seen_preserved(self):
        prev={"jobs":[{"url":"https://z.test/1","first_seen":"2026-01-01"}]}
        code,out=run_pipeline({"arbeitnow.com":GOOD},prev)
        self.assertEqual(out["jobs"][0]["first_seen"],"2026-01-01")
    def test_http_error_recorded_in_health(self):
        err=urllib.error.HTTPError("https://www.reddit.com/x",429,"Too Many",{},None)
        code,out=run_pipeline({"reddit.com":err,"arbeitnow.com":GOOD})
        self.assertEqual(code,0)
        self.assertEqual(out["sources"]["Reddit"]["status"],"failed")
        self.assertIn("429",out["sources"]["Reddit"]["errors"])
if __name__=="__main__": unittest.main()
