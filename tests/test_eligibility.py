import sys,os,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))
from eligibility import classify
def s(loc,desc=""): return classify(loc,desc)["status"]
class T(unittest.TestCase):
    def test_location_open(self):
        for loc in ["Worldwide","Anywhere in the World","Global","Nigeria","West Africa","Sub-Saharan Africa","Remote - Africa"]:
            self.assertEqual(s(loc),"confirmed",loc)
    def test_south_east_africa_not_open(self):
        for loc in ["South Africa","East Africa","Remote, South Africa"]:
            self.assertEqual(s(loc),"excluded",loc)
    def test_specific_places_excluded(self):
        for loc in ["Remote - Hong Kong / South Korea / Japan","Remote, United Kingdom","Remote San Francisco, California","Europe"]:
            self.assertEqual(s(loc),"excluded",loc)
    def test_generic_remote_needs_verification(self):
        self.assertEqual(s("Remote"),"verify");self.assertEqual(s("",""),"verify");self.assertEqual(s("EMEA"),"verify")
    def test_blurb_does_not_confirm(self):
        self.assertEqual(s("Remote","We serve customers worldwide and love our product."),"verify")
    def test_hiring_worldwide_confirms(self):
        self.assertEqual(s("Remote","We are hiring candidates worldwide for this role."),"confirmed")
    def test_explicit_restrictions(self):
        for d in ["US only","Candidates must be located in the US.","Europe only role","UK-based candidates only","You must be authorized to work in the United States.","US citizens only"]:
            self.assertEqual(s("Remote",d),"excluded",d)
    def test_company_description_is_not_restriction(self):
        self.assertEqual(s("Remote","We are a US based company building tools."),"verify")
    def test_nigeria_negative(self):
        self.assertEqual(s("Worldwide","This role is not available in Nigeria."),"excluded")
    def test_nigeria_positive_context(self):
        self.assertEqual(s("Remote","You must be based in Nigeria or West Africa."),"confirmed")
    def test_conflict_flagged(self):
        r=classify("Worldwide","Candidates must be located in the United States.")
        self.assertEqual(r["status"],"verify");self.assertTrue(r["conflict"])
    def test_timezone_alone_not_excluded(self):
        self.assertEqual(s("Remote","Must overlap with US Eastern working hours."),"verify")
    def test_evidence_present(self):
        for loc,d in [("Worldwide",""),("Remote","US only")]:
            self.assertTrue(classify(loc,d)["evidence"])
if __name__=="__main__": unittest.main()
