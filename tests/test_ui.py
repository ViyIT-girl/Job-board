import os,re,json,subprocess,unittest,shutil
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
SRC=open(os.path.join(ROOT,"index.html"),encoding="utf-8").read()
BLOCK=re.search(r"// <merge>(.*?)// </merge>",SRC,re.S).group(1)
def run(js):
    p=subprocess.run(["node","-e",BLOCK+"\n"+js],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)
@unittest.skipUnless(shutil.which("node"),"node not installed")
class T(unittest.TestCase):
    def test_saved_job_survives_leaving_feed(self):
        r=run('''const t={"u1":{job:{url:"u1",title:"EA"},at:"x"}};
        const m=mergeTracked([{url:"u2",title:"Other"}],{u1:"saved"},t);console.log(JSON.stringify(m.all))''')
        self.assertEqual([j["url"] for j in r],["u2","u1"]);self.assertTrue(r[1]["gone"])
    def test_skipped_job_not_retained(self):
        r=run('''const t={"u1":{job:{url:"u1"},at:"x"}};
        console.log(JSON.stringify(mergeTracked([],{u1:"skip"},t).all))''')
        self.assertEqual(r,[])
    def test_unmarked_gone_job_removed(self):
        r=run('''const t={"u1":{job:{url:"u1"},at:"x"}};
        console.log(JSON.stringify(mergeTracked([],{u1:""},t)))''')
        self.assertEqual(r["all"],[]);self.assertEqual(r["tracked"],{})
    def test_snapshot_refreshed_and_created(self):
        r=run('''const m=mergeTracked([{url:"u1",title:"New title"}],{u1:"applied"},{u1:{job:{url:"u1",title:"Old"},at:"keep"}});
        console.log(JSON.stringify(m.tracked))''')
        self.assertEqual(r["u1"]["job"]["title"],"New title");self.assertEqual(r["u1"]["at"],"keep")
        r=run('''console.log(JSON.stringify(mergeTracked([{url:"u9"}],{u9:"saved"},{}).tracked))''')
        self.assertIn("u9",r)
    def test_live_job_not_marked_gone(self):
        r=run('''console.log(JSON.stringify(mergeTracked([{url:"u1"}],{u1:"saved"},{}).all))''')
        self.assertNotIn("gone",r[0])
if __name__=="__main__": unittest.main()
