import sys,os,unittest
sys.path.insert(0,os.path.dirname(__file__))
from test_pipeline import run_pipeline,NOW
HN_STORY={"hits":[{"objectID":"123","title":"Ask HN: Who is hiring? (November 2026)"},{"objectID":"9","title":"Ask HN: Who wants to be hired?"}]}
HN_COMMENTS={"nbPages":1,"hits":[
 {"objectID":"1","parent_id":123,"comment_text":"Acme | Executive Assistant | Remote (Worldwide) | Full-time<p>We are hiring.","created_at":NOW},
 {"objectID":"2","parent_id":999,"comment_text":"Reply | Executive Assistant | REMOTE","created_at":NOW},
 {"objectID":"3","parent_id":123,"comment_text":"Beta | Senior Engineer | Remote","created_at":NOW},
 {"objectID":"4","parent_id":123,"comment_text":"Free text post without pipes about an Executive Assistant role","created_at":NOW}]}
WN=[{"title":"Operations Coordinator","company_name":"WN Co","url":"https://wn.test/1","location":"Anywhere","pub_date":NOW,"description":"x"}]
ROK=[{"legal":"x"},{"position":"Virtual Assistant","company":"RC","url":"https://rok.test/1","location":"Worldwide","date":NOW,"description":"y"}]
class T(unittest.TestCase):
    def setUp(self):
        self.code,self.out=run_pipeline({"workingnomads.com":WN,"search?query=who":HN_STORY,"search_by_date":HN_COMMENTS,"remoteok.com/api":ROK})
    def test_run_ok(self): self.assertEqual(self.code,0)
    def test_working_nomads(self):
        j=[x for x in self.out["jobs"] if x["source"]=="WorkingNomads"]
        self.assertEqual(len(j),1);self.assertEqual(j[0]["eligibility"],"confirmed")
        self.assertEqual(self.out["sources"]["WorkingNomads"]["status"],"ok")
    def test_hn_only_top_level_pipe_posts_with_target_roles(self):
        j=[x for x in self.out["jobs"] if x["source"]=="HackerNews"]
        self.assertEqual([(x["company"],x["title"]) for x in j],[("Acme","Executive Assistant")])
        self.assertEqual(j[0]["eligibility"],"confirmed");self.assertIn("news.ycombinator.com/item?id=1",j[0]["url"])
    def test_remoteok_tag_calls_deduplicated(self):
        j=[x for x in self.out["jobs"] if x["source"]=="RemoteOK"]
        self.assertEqual(len(j),1)
if __name__=="__main__": unittest.main()
